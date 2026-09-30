# FleetTwin deployment runbook

This repository produces a FastAPI backend and a Vite single-page frontend. The
backend exposes `/health` and `/metrics` at the service root; the API itself is
under `/api`. Keep `JWT_SECRET` and `TELEMETRY_KEY` in the platform secret
store, never in Git.

## Render

1. Create a new Render Blueprint from `render.yaml`, or create the backend
   web service with `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`.
2. For Eval 3, set these exact backend service environment variables in Render
   (Production values; do not commit the secret values):

   | Variable | Eval 3 value |
   | --- | --- |
   | `AUTH_ENABLED` | `1` |
   | `SIM_ENABLED` | `1` after the simulator signs packets; otherwise `0` while using signed external ingest |
   | `SIM_SPEED` | `1.0` |
   | `CORS_ORIGINS` | `https://<vercel-project>.vercel.app` (no trailing slash) |
   | `JWT_SECRET` | a generated random secret, at least 32 characters |
   | `TELEMETRY_KEY` | the HMAC key shared with the signed telemetry producer |
   | `AUTH_OPERATOR_PASSWORD` | a strong operator password used for writes/overrides |
   | `AUTH_VIEWER_PASSWORD` | a strong viewer password used for read-only access |
   | `RATE_LIMIT` | `120` |
   | `RATE_LIMIT_WINDOW_S` | `60` |

   `JWT_SECRET` signs login tokens; `TELEMETRY_KEY` signs the contract
   telemetry string. They may be different secrets. The current merged
   `FleetSim` creates `sig=None`, so enabling `TELEMETRY_KEY` before the Lane A
   simulator signer is merged will intentionally drop simulator packets; use
   `SIM_ENABLED=0` for signed external packets or merge the signer first.
3. Confirm the backend health check at
   `https://<backend>.onrender.com/health` and metrics at
   `https://<backend>.onrender.com/metrics`.
4. Render free services can sleep. The scheduled GitHub workflow pings the
   configured `RENDER_HEALTH_URL` every ten minutes.

## Vercel frontend

Import the repository into Vercel, set the project root to `frontend`, and use
the default Vite build (`npm run build`, output `dist`). In Project Settings →
Environment Variables, set these exact variables for both Production and
Preview (use the Production backend URL for Eval 3):

```text
VITE_USE_MOCK=0
VITE_API_URL=https://<backend>.onrender.com
```

Replace the two angle-bracket placeholders with the actual project/backend
hostnames, then set Render `CORS_ORIGINS` to the exact Vercel origin. Deploy the
backend on Render, Docker, or Kubernetes separately; Vercel does not run the
FastAPI process. Log in to Eval 3 with the Render-configured operator or viewer
credentials.

## Docker Compose

From the repository root:

```powershell
docker compose up --build
```

The dashboard is at `http://localhost:8080`, the backend at
`http://localhost:8000`, and backend data is stored in the named
`fleettwin-data` volume. Set `JWT_SECRET`, `TELEMETRY_KEY`, `AUTH_ENABLED`,
and ports in a local `.env` file. To start the optional Redis service:

```powershell
docker compose --profile redis up --build
```

Redis is an optional deployment building block; the default process-local
limiter and cache do not require it.

## Kubernetes

Build and publish images matching the image names in `k8s/*-deployment.yaml`,
or replace those names with your registry paths. Install an NGINX ingress
controller and metrics-server first, then create secrets out-of-band:

```powershell
kubectl create namespace fleettwin
kubectl -n fleettwin create secret generic fleettwin-secrets `
  --from-literal=JWT_SECRET="<random-secret>" `
  --from-literal=TELEMETRY_KEY="<random-secret>"
kubectl apply -n fleettwin -f k8s/configmap.yaml
kubectl apply -n fleettwin -f k8s/backend-deployment.yaml
kubectl apply -n fleettwin -f k8s/frontend-deployment.yaml
kubectl apply -n fleettwin -f k8s/ingress.yaml
kubectl apply -n fleettwin -f k8s/hpa.yaml
```

Do not apply `secret.example.yaml` to a production cluster; the command above
creates the real Secret first. Replace `fleettwin.example.com` and
`fleettwin-tls` in the ingress with the actual DNS name and certificate secret.
The HPA requires metrics-server and scales the backend from one to three pods
at 70% average CPU.

## Operational checks

- `GET /health` returns status and ingest/drop information.
- `GET /metrics` exposes request latency, ingest rate, dropped packets, and
  active alert, ingest age, and fleet sync gauges in Prometheus text format.
- Keep `AUTH_ENABLED=0` only for local mock/demo use. In deployed environments,
  use a strong `JWT_SECRET`, configure `TELEMETRY_KEY`, and restrict
  `CORS_ORIGINS` to the frontend origin.

## Prometheus alerting

`ops/prometheus.yml` scrapes the backend every 15 seconds and loads
`ops/alerts.yml`. The rules page alerts when the backend is down, telemetry has
stopped arriving for two minutes, more than 10% of packets are dropped over
five minutes, or the fleet sync score stays below 80 for five minutes. Mount
both files into Prometheus, or copy the rules into an existing Prometheus
configuration and route alerts through the team's Alertmanager.

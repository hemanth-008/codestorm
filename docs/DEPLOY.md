# FleetTwin deployment runbook

This repository produces a FastAPI backend and a Vite single-page frontend. The
backend exposes `/health` and `/metrics` at the service root; the API itself is
under `/api`. Keep `JWT_SECRET` and `TELEMETRY_KEY` in the platform secret
store, never in Git.

## Render

1. Create a new Render Blueprint from `render.yaml`.
2. Set the generated backend `JWT_SECRET` and `TELEMETRY_KEY` values in the
   service Environment page. Set `AUTH_ENABLED=1` only after operator and
   viewer credentials are configured.
3. Confirm the backend health check is green at
   `https://<backend>.onrender.com/health` and inspect
   `https://<backend>.onrender.com/metrics`.
4. Update `CORS_ORIGINS` and the frontend `VITE_API_URL` if Render assigns
   different service names or a custom domain.
5. Render free services can sleep. The scheduled GitHub workflow pings the
   configured `RENDER_HEALTH_URL` every ten minutes.

## Vercel frontend

Import the repository into Vercel, set the project root to `frontend`, and use
the default Vite build (`npm run build`, output `dist`). Set:

```text
VITE_USE_MOCK=0
VITE_API_URL=https://<backend-host>
```

Add the Vercel origin to the backend `CORS_ORIGINS` value. Deploy the backend
on Render, Docker, or Kubernetes separately; Vercel does not run the FastAPI
process.

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
  active alert gauges in Prometheus text format.
- Keep `AUTH_ENABLED=0` only for local mock/demo use. In deployed environments,
  use a strong `JWT_SECRET`, configure `TELEMETRY_KEY`, and restrict
  `CORS_ORIGINS` to the frontend origin.

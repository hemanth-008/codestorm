# Security and Environment Variables

FleetTwin's backend security is controlled entirely via environment variables.
When none are set, the app runs in **open demo mode** — no auth, no telemetry
signing, CORS allows all origins.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AUTH_ENABLED` | `0` | Set to `1` to require JWT authentication on write endpoints. |
| `JWT_SECRET` | `fleettwin-development-secret` | HMAC-SHA256 signing key for JWT tokens. **Change in production.** |
| `TELEMETRY_KEY` | *(unset)* | When set, every inbound telemetry packet must carry an HMAC signature. Invalid packets are dropped and a `spoof_suspected` event is emitted. The simulator signs its own packets with the same key. |
| `AUTH_OPERATOR_PASSWORD` | `operator` | Password for the built-in `operator` user. |
| `AUTH_VIEWER_PASSWORD` | `viewer` | Password for the built-in `viewer` user. |
| `AUTH_USERS` | *(unset)* | Optional JSON object to add extra users: `{"alice": {"password": "...", "role": "operator"}}` |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins, e.g. `https://fleettwin.onrender.com`. |
| `SIM_ENABLED` | `1` | `0` disables the built-in simulation loop. |
| `SIM_SPEED` | `1.0` | Simulation speed multiplier (2.0 = 2× real-time). |
| `DB_URL` | `sqlite:///./fleettwin.db` | Database connection string. |
| `RATE_LIMIT` | `120` | Max API requests per window per client+path. |
| `RATE_LIMIT_WINDOW_S` | `60` | Rate-limit window in seconds. |

## Roles

| Role | Can read (GET) | Can write (POST) |
|---|---|---|
| `operator` | ✔ | ✔ |
| `viewer` | ✔ | ✘ (403) |

## Public Endpoints (no token needed even with `AUTH_ENABLED=1`)

- `GET /health`
- `GET /metrics`
- `GET /api/stream` (SSE)
- `POST /api/auth/login`
- `POST /api/telemetry` (protected by `TELEMETRY_KEY` signature instead)

## Demo Credentials (defaults)

| Username | Password | Role |
|---|---|---|
| `operator` | `operator` | operator |
| `viewer` | `viewer` | viewer |

## Render Configuration

Set these in the Render dashboard under **Environment → Secret Files / Environment Variables**:

```
AUTH_ENABLED=1
JWT_SECRET=<generate-a-random-32-char-string>
TELEMETRY_KEY=<generate-a-random-32-char-string>
CORS_ORIGINS=https://fleettwin.onrender.com
AUTH_OPERATOR_PASSWORD=<strong-password>
AUTH_VIEWER_PASSWORD=<strong-password>
```

For the demo/hackathon evaluation, you can use the defaults:

```
AUTH_ENABLED=0
```

This skips all authentication and lets the evaluators interact freely.

## Login Flow

```
POST /api/auth/login
Content-Type: application/json

{"username": "operator", "password": "operator"}
```

Response:

```json
{"access_token": "eyJ...", "role": "operator"}
```

Use the token in subsequent requests:

```
Authorization: Bearer eyJ...
```

Tokens expire after 1 hour (3600 s).

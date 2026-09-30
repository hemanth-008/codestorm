# FleetTwin CONTRACT

Read-only for agents. Only Hemanth changes it. Types live in `backend/app/contract/schemas.py`, constants and shared formulas in `backend/app/contract/physics.py`.

## 1. Conventions

- Arena: 200 x 200 m, origin (0,0) bottom-left, heading in radians CCW from +x. The existing map code must be adapted to these metric coordinates.
- Fleet: `R1` rover, `D1` drone, `G1` AGV. Sim step and telemetry period `DT = 0.2 s` (5 Hz). All `ts` are simulation seconds.
- JSON over the wire is exactly the Pydantic models in `schemas.py`.

## 2. Lanes and file ownership

| Lane | Agent | Owns (edit only these) |
|---|---|---|
| A core | Antigravity #1 | `backend/main.py`, `backend/app/{sim,twin,api}/`, `backend/app/core/{bus,db,pipeline}.py`, `backend/tests/{sim,twin,core}/` |
| B analytics | Codex | `backend/app/{detect,health,decision,sandbox,evalsuite}/`, `backend/tests/{detect,health,decision,sandbox,evalsuite}/` |
| C frontend | Antigravity #2 | everything under `frontend/` |
| D ops | Codex #2 | `backend/app/{security,observability}/`, `backend/app/core/cache.py`, `backend/tests/{security,obs}/`, `.github/`, `Dockerfile*`, `docker-compose.yml`, `k8s/`, `ops/`, `docs/DEPLOY.md`, `render.yaml` |
| Hemanth | human | `AGENTS.md`, `CONTRACT.md`, `EXECUTION_PLAN.md`, `HANDOFF.md` (each lane may append to its own heading), `backend/app/contract/*` |

`backend/requirements.txt` is shared, append-only.

## 3. Module interfaces (Python)

```python
# sim (Lane A)
class RobotModel:                                   # sim/models.py
    def step(self, s: StateVec, cmd: Command, dt: float, wear: float = 0.0) -> StateVec: ...
def make_model(robot_type: RobotType) -> RobotModel
class Command(BaseModel): speed: float; yaw_rate: float
def follow(s: StateVec, wps: list[Waypoint], idx: int, cruise: float,
           robot_type: RobotType) -> tuple[Command, int, bool]   # sim/control.py; (cmd, new_idx, done)

class FleetSim:                                     # sim/world.py
    now: float
    def __init__(self, seed: int = 42, wear_rate_scale: float = 1.0, robots: list | None = None): ...
    def step(self, dt: float = DT) -> list[Telemetry]   # packets that ARRIVE this step (after faults; dropped ones omitted)
    def assign_mission(self, m: Mission) -> None
    def missions(self) -> dict[str, Mission]
    def inject(self, spec: AttackSpec) -> None
    def clear(self, robot_id: str | None = None) -> None
    def ground_truth(self, robot_id: str) -> GroundTruth

# twin (Lane A), one instance per robot
class TwinEngine:                                   # twin/engine.py
    def __init__(self, robot_id: str, robot_type: RobotType): ...
    def set_mission(self, m: Mission | None) -> None
    def on_telemetry(self, tel: Telemetry) -> TwinState
    def tick(self, now: float) -> TwinState | None  # call every step; enters dead_reckoning after DROPOUT_TIMEOUT_S
    def snapshot(self) -> TwinSnapshot

# analytics (Lane B), one instance per robot unless noted
class DeviationDetector:  def update(self, twin: TwinState) -> list[Event]
class SpoofGuard:         def update(self, tel: Telemetry, twin: TwinState) -> list[Event]  # keeps its own previous packet
class NoiseMonitor:       def update(self, twin: TwinState) -> list[Event]
class HealthEstimator:    def update(self, tel: Telemetry, twin: TwinState) -> HealthReport
def decide(robot_id: str, twin: TwinState, health: HealthReport,
           recent_events: list[Event], override: OverrideState | None) -> Decision   # decision/engine.py
def simulate_mission(snap: TwinSnapshot, mission: Mission,
                     health: HealthReport | None = None) -> SimResult                 # sandbox/simulate.py
def run_suite(seed: int = 42, fast: bool = True) -> EvalResult                        # evalsuite/runner.py

# ops (Lane D)
security/signing.py:  sign_telemetry(tel, key) -> str ; verify_telemetry(tel, key) -> bool
security/install.py:  install(app) ; observability/install.py: install(app)
core/cache.py:        ttl_cache(seconds) decorator
```

Signature string: HMAC-SHA256 over `f"{robot_id}|{seq}|{ts:.3f}|{x:.3f}|{y:.3f}|{speed:.3f}|{battery:.2f}"`, hex digest in `Telemetry.sig`.

## 4. Pipeline order (Lane A `core/pipeline.py`, per arriving packet)

1. If `TELEMETRY_KEY` is set: verify signature. Invalid: drop the packet and emit `spoof_suspected` (critical, "bad signature").
2. `twin.on_telemetry`.
3. `SpoofGuard.update`, `NoiseMonitor.update`, `DeviationDetector.update`.
4. `HealthEstimator.update`.
5. `decide(...)`.
6. Persist to DB, publish events on the bus, include in the next `StreamFrame`.

Every sim step, also call `twin.tick(now)` for each robot so dropouts are noticed.

## 5. Behaviour rules

- **Twin residual** is observed minus the one-step-ahead prediction made before the packet was seen. The estimator is predict-then-correct with gain 0.6; if `residual_pos > GATE_M` the gain drops to 0.1 so spoofed jumps do not drag the twin (twin acts as verifier).
- **Sync score:** `100 * clamp(1 - rmse_pos / SYNC_TOL_M, 0, 1)`, RMSE over the last `SYNC_WINDOW` packets. In `dead_reckoning`, `confidence = exp(-t_since_packet / 8 s)` and `sync_score <= 100 * confidence`.
- **Dropout:** Lane A emits `dropout` (warn) on entering dead_reckoning and `link_recovered` (info) on the next packet.
- **Events fire on state transitions only** (rising edge, then a `*_cleared` edge), max one event per kind per robot per 5 s.
- **Lane A** emits: `dropout`, `link_recovered`, `mission_deployed`, `override`, `attack_injected`, `attack_cleared`. **Lane B** emits: `deviation`, `deviation_cleared`, `spoof_suspected`, `noise_high`, `noise_cleared`, `health_warning`, `maintenance_due`.
- **Decision actions** (override buttons use `CONTINUE`, `REROUTE`, `RETURN_TO_BASE`): keep the existing `/api/decision` response shape `{action, reason, confidence}`; per-robot decisions add `robot_id`.
- **Safety gate (sandbox):** `safe_to_deploy` is false if end battery < 15 %, predicted path leaves the arena, RUL < mission ETA, or any speed/accel limit in `LIMITS` is exceeded.

## 6. Detection targets (used as test thresholds and scorecard)

| Scenario | Target |
|---|---|
| `spoof_freeze` | detected within 3 s |
| `spoof_jump` >= 15 m | detected on the first packet |
| `spoof_drift` >= 0.5 m/s | detected within 15 s |
| `spoof_battery` >= 10 % | detected within 2 s |
| `noise` sigma >= 1 m | `noise_high` within 5 s |
| `dropout` 2/5/10 s | twin enters and leaves dead_reckoning, position error stays under 6 m, recovery to sync >= 80 within 5 s |
| clean run | fewer than 1 false alarm per robot per 5 min |
| RUL | error under 25 % once health_index < 0.7 |

## 7. HTTP API (all under `/api`)

| Method and path | Purpose |
|---|---|
| `GET /stream` | SSE, one `StreamFrame` JSON per message at 5 Hz |
| `GET /fleet` | `list[RobotFrame]` |
| `GET /robots/{id}` | `{frame: RobotFrame, history: last 120 TwinState, events: last 50 Event}` |
| `GET /events?limit=50` | `list[Event]` |
| `GET /decision?robot_id=` | `Decision` (fleet-level if omitted; existing route, keep working) |
| `POST /override` | body `{robot_id?, action, seconds=15}` returns `OverrideState` (existing route, keep working) |
| `POST /telemetry` | body `Telemetry`, returns 202 |
| `POST /attacks/inject`, `POST /attacks/clear` | body `AttackSpec` / `{robot_id?}` |
| `GET /missions`, `POST /missions/simulate`, `POST /missions/deploy` | `Mission` in, `SimResult` out; deploy refuses unless `safe_to_deploy` (or `?force=1`) |
| `POST /eval/run?seed=`, `GET /eval/latest` | `EvalResult` (run must finish in 15 s or less) |
| `POST /auth/login` | body `{username, password}` returns `Token` |
| `GET /health`, `GET /metrics` | health JSON, Prometheus text (mounted at root, not under `/api`) |

## 8. Environment variables

`AUTH_ENABLED` (default 0), `JWT_SECRET`, `TELEMETRY_KEY` (unset = unsigned), `SIM_ENABLED` (1), `SIM_SPEED` (1.0), `DB_URL` (`sqlite:///./fleettwin.db`), `CORS_ORIGINS`, `VITE_API_URL`, `VITE_USE_MOCK` (1 = frontend uses its built-in mock stream).

## 9. Change protocol

Contract changes come only from Hemanth, in a commit to `main`. Lanes pull them by merging `main` into their branch. Two lanes disagreeing on a shape means the contract file wins.

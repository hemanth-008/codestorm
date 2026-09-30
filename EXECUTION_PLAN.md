# FleetTwin Execution Plan (parallel agents)

## Lanes

| Lane | Agent | Worktree / branch | Role |
|---|---|---|---|
| A core | Antigravity #1 | `C:\dev\ft-core` / `lane-core` | Simulator, twin engine, pipeline, API. **Critical path.** |
| B analytics | Codex | `C:\dev\ft-analytics` / `lane-analytics` | Detectors, health/RUL, decision, sandbox, eval suite. Pure Python + tests. |
| C frontend | Antigravity #2 | `C:\dev\ft-frontend` / `lane-frontend` | Dashboard, built against a mock stream first. |
| D ops | Codex #2 | `C:\dev\ft-ops` / `lane-ops` | Security, CI/CD, observability, Docker, k8s. Start after B and C are running. |

`C:\dev\codestorm` (branch `main`) is the integration and demo tree. Agents never edit it. Render and Vercel deploy from `main`, so the live site stays stable between checkpoints.

## Kickoff prompt (paste into each agent, fill the two blanks)

```
You are the LANE __ agent on the FleetTwin repo (worktree: __). Read AGENTS.md, CONTRACT.md and your lane section of EXECUTION_PLAN.md completely. Then execute your task queue in order without waiting for me: after each task run the tests, commit, push your branch and continue. Edit only the files your lane owns. Log blockers and contract questions in HANDOFF.md and keep going with the simplest workaround. Start now with task __.
```

## Human runbook (Hemanth)

Your jobs: contract owner, integrator, demo driver. Do not code lane work yourself.

| Checkpoint | Target | Do |
|---|---|---|
| CP0 | T+0 | Commit the kit, create worktrees, kick off A, C, B (D once one agent frees up) |
| CP1 | before Eval 1 (2:30 PM) | A1-A3, B0-B3, C1-C2 done. Send C2 screenshots (mock data is fine) to your teammate for the wireframe slide by 1:15 PM |
| CP2 | about 6:00 PM | A4 done. Tell agent A to start A5 (merges B and D, wires everything). Tell agent C to start C8 (connect to the real backend) |
| CP3 | 8:30 PM freeze, Eval 2 at 9:30 PM | Merge lane-core into `main`, deploy, warm up Render, rehearse the demo: ingest, twin, deviation, sync score, noise and dropout injection, DB |
| Overnight | 10:30 PM onward | Queue B6, D1-D3 wiring, C7 and let agents run while you sleep about 2:00-5:30 AM. Set each agent's terminal policy to auto-approve inside its worktree so it does not stall on prompts |
| CP4 | 5:30-9:00 AM (Eval 3 at 9:30 AM) | Review overnight commits, merge, enable `AUTH_ENABLED` and `TELEMETRY_KEY` in the deployed backend, confirm CI is green |
| CP5 | before Eval 4 (2:30 PM) | D4-D6 merged, monitoring page live, scorecard tested, rehearsal |

Merge order at every checkpoint, in the `main` tree, one command at a time: `git merge lane-core`, `git merge lane-analytics`, `git merge lane-ops`, `git merge lane-frontend`. Then run the backend tests, start both servers, and click through the smoke checklist: fleet map moves, sync score shows, inject noise and see the alert, inject dropout and see dead_reckoning then recovery, mission simulate works, scorecard runs.

**If behind, cut in this order:** sandbox polish, ML in health (keep trend regression), k8s manifests, Redis, monitoring page. **Never cut:** sync score, deviation detection, attack injection, scorecard.

**Credits:** protect lanes A, C and B first. Give D the cheapest capable model setting.

---

## Lane A: core (Antigravity #1)

**A1. Simulator core** (`sim/models.py`, `sim/control.py`, `sim/world.py`)
- Rover (unicycle), drone (2D point-mass, fixed altitude 20 m, wind gusts), AGV (limited yaw rate). `make_model`. Respect `LIMITS`.
- `follow()` pure pursuit (lookahead 4 m, waypoint reached within 3 m, loop supported).
- `FleetSim` per CONTRACT. Default fleet `R1`, `D1`, `G1` on looping missions inside the arena. Two circular obstacles on or near paths: robots swerve laterally (radius + 2 m) then rejoin, producing real deviation.
- Battery, current, temperature, vibration and wear generated from `physics.py`. Wear rises linearly; defaults make R1 fail near 12 min, D1 near 15, G1 near 20 of sim time; `wear_rate_scale` speeds this up. At wear >= 1 the robot stops.
- `ground_truth()`.
- Done when: same seed gives identical output, 5 min of headless sim runs in under 3 s, all telemetry within `LIMITS`, current/temp/vibration visibly rise with wear, tests pass.

**A2. Faults** (`sim/faults.py`, wired into `FleetSim.step/inject/clear`)
- `noise`: Gaussian sigma on x, y, speed, current, temp, scaled by `magnitude`. `dropout`: packets omitted for `duration_s`. `spoof_freeze`: replay last values with advancing seq and ts. `spoof_jump`: add `magnitude` m to position. `spoof_drift`: position offset grows at `magnitude` m/s. `spoof_battery`: battery offset by `magnitude` %.
- Attacks alter the packets only, never the true robot. Attacks expire after `duration_s`. `ground_truth().attack_active` reports the current one.
- Done when: each kind has a test showing the packet stream changes as specified and truth is unaffected.

**A3. Twin engine** (`twin/engine.py`)
- Predict-then-correct per CONTRACT section 5: prediction from `make_model` + `follow` on the assigned mission, gain 0.6, gated gain 0.1 above `GATE_M`, thermal/battery/current predictions from `physics.py` (no wear).
- Compute residuals, `cross_track_err`, `heading_err`, `plan_x/plan_y`, sync score, dead_reckoning mode with confidence decay, `snapshot()`.
- Done when: clean 5 min run has sync above 90, a 5 s dropout enters dead_reckoning with position error under 6 m and returns to synced, a 20 m jump produces a residual spike without dragging the estimate.

**A4. Pipeline and API** (`core/bus.py`, `core/db.py`, `core/pipeline.py`, `api/*`, `main.py`)
- Background asyncio loop running the sim at `SIM_SPEED`, feeding the pipeline. `POST /api/telemetry` feeds the same pipeline. Event bus, SQLite persistence (tables: robots, telemetry, twin_state, events, missions, eval_runs, users), SSE `/api/stream`, `/api/fleet`, `/api/robots/{id}`, `/api/events`, `/api/attacks/*`, `/api/missions` (simulate and deploy call sandbox when available, otherwise return 501), `/api/decision` and `/api/override` kept backward compatible, CORS from `CORS_ORIGINS`.
- Until Lane B lands, use trivial stand-ins behind the same interfaces so the stream works end to end.
- Done when: `/api/stream` emits valid `StreamFrame`s at 5 Hz, an injected dropout shows up as events, and an API smoke test passes.

**A5. Merge and wire** (start when Hemanth says)
- Merge `lane-analytics` and `lane-ops` into `lane-core`, resolve conflicts (their files win inside their lanes). Replace stand-ins with the real detectors, health, decision, sandbox, eval endpoints; call `security.install(app)` and `observability.install(app)`; sign telemetry when `TELEMETRY_KEY` is set.
- Done when: the full smoke checklist in the runbook passes locally.

**A6. Hardening.** Stream backpressure, graceful shutdown, error handling for malformed packets, end-to-end smoke script `scripts/smoke.ps1`.

---

## Lane B: analytics (Codex)

**B0. Test fixtures** (`backend/tests/fixtures.py`): synthetic telemetry stream generators (clean, noisy, spoofed per kind, dropout, wear ramp) built only from `schemas.py` and `physics.py`, so Lane B needs nothing from Lane A until B5.

**B1. Deviation** (`detect/deviation.py`): flag when `cross_track_err` or `heading_err` stays above threshold for N packets; tag the likely cause in `detail` (`obstacle`, `navigation`, `sensor`); emit `deviation` and `deviation_cleared`. Tests on fixtures.

**B2. Spoof and noise** (`detect/spoof.py`, `detect/noise.py`): sequence and timestamp checks, implied speed vs reported speed, accel and yaw limits from `LIMITS`, battery rising or mismatching `expected_drain_pct_per_s`, frozen values while the twin predicts motion, persistent twin residual with sane-looking packets (drift). `NoiseMonitor` from rolling residual variance. Must meet CONTRACT section 6 targets on fixtures.

**B3. Health and RUL** (`health/health.py`): from current vs `expected_current`, temperature vs `expected_temp_step`, vibration vs `expected_vibration`, derive a wear estimate, health index and a robust trend regression giving `rul_s` with `rul_low_s/rul_high_s`; set `status` and emit `health_warning` and `maintenance_due`. RUL error under 25 % on the wear-ramp fixture once health_index < 0.7.

**B4. Decision engine** (`decision/engine.py`): rule-based fusion of twin mode, deviation, spoof, health and overrides into `Decision` with a human-readable reason and confidence. Read the existing decision logic in `backend/main.py` and preserve its behaviour; add per-robot decisions. Spoofed telemetry gives `QUARANTINE_TELEMETRY`, low RUL gives `SCHEDULE_MAINTENANCE` or `RETURN_TO_BASE`.

**B5. Sandbox** (`sandbox/simulate.py`): needs `sim/models.py` and `sim/control.py` from Lane A (merge `lane-core` first). Fork the snapshot, run the mission with `make_model` and `follow` at dt 0.5, compute ETA, end battery, risk and violations, apply the safety gate from CONTRACT section 5.

**B6. Eval suite** (`evalsuite/scenarios.py`, `evalsuite/runner.py`): needs A1-A3 merged. Headless, seeded scenarios for noise (3 levels), dropout (2/5/10 s), each spoof kind, plus clean baselines; measure detection, time-to-detect, false alarms, min sync, recovery time, and RUL error against `ground_truth()`. `run_suite()` must finish within 15 s. Add CLI `python -m app.evalsuite.runner`.

---

## Lane C: frontend (Antigravity #2)

Work in `frontend/` only. Set `VITE_USE_MOCK=1` until C8.

**C1. Foundation:** typed API client and `useFleetStream()` hook (SSE) mirroring `schemas.py`; a built-in mock stream generator emitting realistic `StreamFrame`s (3 robots moving in the 200 m arena, occasional events); app shell with routes and nav in the existing design system.

**C2. Fleet overview:** metric-arena map with dashed ghost planned path vs solid actual trail per robot, type-specific markers, robot cards (sync bar, battery, mode badge, health/RUL badge), live alert feed, fleet sync gauge. Adapt the existing patrol-map code.

**C3. Robot detail:** twin-vs-real charts (position residual, battery, temperature expected vs observed, vibration), health gauge with RUL range, decision "why" panel with the three override buttons (keep existing behaviour).

**C4. Adversarial panel:** per-robot inject buttons with magnitude and duration controls, live detection status chips driven by events, clear-all button.

**C5. Scorecard:** "Run attack suite" button, loading state, summary tiles (detection rate, false alarms/hour, mean time-to-detect, mean recovery, RUL error, mean sync clean vs attacked), per-scenario table, one bar chart.

**C6. Sandbox:** click-to-add waypoints on the map, robot picker, Simulate, overlay the predicted path, show ETA, end battery, risk, violations; Deploy disabled unless `safe_to_deploy`.

**C7. Login and monitoring:** login page only when auth is on; monitoring page (health JSON, ingest stats from the stream); "backend is waking up" banner for the sleeping Render free tier; empty and error states; mobile-tolerant layout.

**C8. Connect to the real backend** (start when Hemanth says): switch `VITE_USE_MOCK=0`, fix contract mismatches, verify every page against the live stream.

---

## Lane D: ops (Codex #2)

**D1. Security** (`security/`): `signing.py` (per CONTRACT), JWT auth with `operator` and `viewer` roles behind `AUTH_ENABLED`, `/api/auth/login`, simple in-memory rate limiter, `security.install(app)`. Start with `signing.py` so Lane A can import it. Tests included.

**D2. CI and keep-warm** (`.github/workflows/`): CI running backend pytest and the frontend build on every push and PR; a scheduled workflow pinging the Render backend `/health` every 10 minutes.

**D3. Observability and cache** (`observability/`, `core/cache.py`): `/health`, `/metrics` (Prometheus format: request latency, ingest rate, dropped packets, active alerts), `observability.install(app)`, `ttl_cache` decorator.

**D4. Docker:** backend Dockerfile, frontend Dockerfile (nginx), `docker-compose.yml` (backend, frontend, optional redis), `.dockerignore`.

**D5. Kubernetes:** `k8s/` deployment, service, configmap, ingress, HPA; `render.yaml`; `docs/DEPLOY.md` covering Render, Vercel, Docker and k8s.

**D6. Alerting:** `ops/prometheus.yml` and `ops/alerts.yml` (ingest lag, drop rate, backend down, low fleet sync), documented in `docs/DEPLOY.md`.

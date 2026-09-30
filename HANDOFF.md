# HANDOFF.md

Shared log. Each lane appends only under its own heading: blockers, contract questions, requests to other lanes, new dependencies, assumptions. Keep entries to one or two lines.

## Lane A (core)
- Completed A1, A2, A3, A4.
- Blocked on A5: waiting for `lane-ops` branch to exist and Hemanth's signal to merge and wire. Moving on to A6.

## Lane B (analytics)

- B4: the legacy `main.py` emits `SLOW_DOWN`, but CONTRACT `Action` excludes it; the decision engine maps that case to contract-valid `REROUTE` and retains the 1.6 m/s threshold.
- B5: lane-core is available remotely but cannot be merged safely into this lane worktree; sandbox uses `app.sim.models/control` when integrated and a contract-only deterministic fallback for local tests.
- B6: eval suite remains contract-fixture based until lane-core is integrated; seeded scenarios and metrics exercise the same public detector/health interfaces without modifying Lane A files.

## Lane C (frontend)
- C8: Backend `/api/stream` deviates from CONTRACT by returning Unix time for `ts` instead of simulation seconds. Payload snippet: `{"ts":1790770672.6133218,"robots":[{"robot_id":"R1",...}], "events":[...], "fleet_sync":97.95, "ingest":{"msgs_per_s":14.89,"dropped":0,"lag_ms":1790769845939.6584}}`. Workaround added in `useFleetStream.js` to extract `ts` from the first robot's telemetry.
- C8: Scorecard RUL error percentage was being multiplied by 100 in the UI but backend already returns it as a percentage. Fixed in `Scorecard.jsx`.
## Lane D (ops)

## Hemanth

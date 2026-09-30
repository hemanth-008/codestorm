# FleetTwin validation results

Run on `lane-analytics` after merging `main`; `run_suite(seed=1..5, fast=True)`.
All times are simulation seconds. RUL error is the maximum absolute percentage
error after the estimator reports `health_index < 0.7`; the estimator receives
only noisy telemetry and twin state. The linear wear ramp is retained by the
scorekeeper only as evaluation truth.

| Target | Contract | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Seed 5 | Result |
|---|---|---:|---:|---:|---:|---:|---|
| Freeze detection | <= 3 s | 0.0 s | 0.0 s | 0.0 s | 0.0 s | 0.0 s | PASS |
| Jump detection | <= 1 packet (0.2 s) | 0.0 s | 0.0 s | 0.0 s | 0.0 s | 0.0 s | PASS |
| Drift detection | <= 15 s; spoof detector | 5.4 s | 5.4 s | 5.4 s | 5.4 s | 5.4 s | PASS |
| Battery spoof | <= 2 s | 0.0 s | 0.0 s | 0.0 s | 0.0 s | 0.0 s | PASS |
| Noise (1 m sigma) | <= 5 s | 0.8 s | 0.8 s | 0.8 s | 1.0 s | 0.8 s | PASS |
| Dropout 2 s | error < 6 m; re-sync <= 5 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | PASS |
| Dropout 5 s | error < 6 m; re-sync <= 5 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | PASS |
| Dropout 10 s | error < 6 m; re-sync <= 5 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | 1.2 m / 0.0 s | PASS |
| Clean false alarms | < 1 / robot / 5 min | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | PASS |
| RUL error with sensor noise | < 25% after health < 0.7 | 12.34% | 18.99% | 8.46% | 8.71% | 21.97% | PASS |

Dropout cells are `max position error / seconds from reconnect until sync >= 80`.
The RUL noise envelope is seeded and channel-specific: position 0.02 m, speed
0.008 m/s, battery 0.03%, temperature 0.10 degC, current 0.02 A, vibration
0.003 g RMS. Clean runs produced zero false alarms.

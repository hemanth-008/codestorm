# AGENTS.md: rules for every AI agent on FleetTwin

FleetTwin is a real-time digital twin for a heterogeneous robot fleet (rover, drone, AGV): twin prediction vs observed telemetry drives deviation detection, spoof/noise/dropout handling, failure prediction (RUL), a mission what-if sandbox and an attack-suite scorecard. Hackathon: 36 hours, four evaluations. **Speed matters, but the contract matters more.**

Read `CONTRACT.md` and your lane section in `EXECUTION_PLAN.md` fully before writing code.

## Rules

1. **One lane per agent.** Your lane and its file ownership are set in your kickoff prompt (see CONTRACT.md section 2). Edit only files you own. Reading other lanes' files is fine.
2. **Never edit `backend/app/contract/*`.** Import from it. If the contract is wrong or insufficient, log it in `HANDOFF.md` under your lane, use the simplest workaround, and keep going.
3. **Need something from another lane?** Write a request in `HANDOFF.md`, code against the interface in CONTRACT.md with a stub or fixture, and continue. Do not wait.
4. **Work the queue in order.** After each task: run the tests, commit (`lane<X>: <task id> <summary>`), push your branch, then start the next task without waiting for me unless you are blocked.
5. **Tests are part of done.** Every backend module ships with pytest tests under `backend/tests/<area>/`. Deterministic seeds only. Tests must pass before you commit.
6. **Environment is Windows + PowerShell.** Python: use the shared venv by full path, run from your worktree's `backend` folder: `C:\dev\codestorm\backend\venv\Scripts\python.exe -m pytest`. Node 18+. Run one command per call (no `&&`, no bash-only syntax).
7. **No long blocking commands.** Start dev servers in the background, use timeouts, never leave a foreground server running.
8. **Dependencies:** add to `backend/requirements.txt` (append only) or `frontend/package.json`, and note it in `HANDOFF.md`.
9. **Git safety:** never force-push, never push to `main`, never commit `.env`, secrets, venvs, `node_modules`, databases or datasets.
10. **Units:** meters, seconds, radians, battery %, degC, amps, g RMS. Time is simulation seconds.
11. **Ambiguity:** choose the simplest option that satisfies the contract, note it in `HANDOFF.md`, move on. Do not stop to ask.
12. **Code style:** type hints, small functions, a docstring with the formula for anything numerical, comments explain why.
13. **Frontend design system:** keep the "drawing sheet" look: paper `#F1EEE4`, ink `#161616`, signal orange `#FF5A1F`, Bahnschrift for headings, Consolas for numbers. Reuse existing components before writing new ones.
14. **Final message of every task, 5 lines max:** what changed, how to verify, open issues.

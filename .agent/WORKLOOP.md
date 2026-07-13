# Current work loop

Objective:
Keep monitor work moving through small, committed, resumable loops with GitHub as source of truth.

Completed loops:
- Loop 6 — configured file-backend follow logs.
- Loop 7 — explicit systemd/journalctl-style monitor backend.

Loop 6 result:
`[monitor] backend = file` with `log_file = ...` can show recent lines and `modelctl monitor router --follow` streams appended lines until interrupted.

Loop 7 result:
`[monitor] backend = systemd` with `service = ...` can show recent journal lines and `modelctl monitor router --follow` delegates to a `journalctl -u <service> -f` style read-only command.

Files changed across these loops:
- modelctl.py
- tests/test_storage_monitor.py
- docs/backlog.md
- docs/phase-6-monitor-discovery.md
- README.md
- .agent/WORKLOOP.md

Out of scope preserved:
- broad process scanning
- service-name guessing
- router start/stop/restart behavior
- archive / restore / delete / recover flows
- benchmark / recommend flows
- GPU/model-management changes

Validation run:
- `python -m py_compile modelctl.py tests/test_storage_monitor.py`
- `python -m unittest tests.test_storage_monitor -v`
- `python -m unittest discover -s tests -v`
- `python scripts/check_private_markers.py`
- `git diff --check`

Next loop:
Loop 8 — reconcile port-centric monitor examples with real commands.

Loop 8 recommended slice:
1. Inspect current `tail` command implementation and monitor help examples.
2. Decide whether `modelctl tail 8080` should become real, be redirected to monitor, or be removed from examples until backed by implementation.
3. If adding behavior, use explicit configured mapping only; do not scan processes or guess service names.
4. Add tests first for help/examples and the chosen command behavior.
5. Keep all monitor/tail behavior read-only.

Loop 8 acceptance criteria:
- no help example points at an unsupported command
- the journalctl-like path for `llama-cuda.service` remains available through explicit systemd config
- JSON snapshot behavior remains stable
- follow behavior remains non-JSON and clear

Blocker:
None for Loop 8 planning. The implementation should stay narrow and configured-only.

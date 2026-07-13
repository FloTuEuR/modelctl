# Current work loop

Objective:
Keep monitor work moving through small, committed, resumable loops with GitHub as source of truth.

Completed loops:
- Loop 6 — configured file-backend follow logs.
- Loop 7 — explicit systemd/journalctl-style monitor backend.
- Loop 8 — port-centric `tail` example reconciled with real configured behavior.
- Loop 9 — unsupported restart examples removed from monitor/read-only guidance.

Loop 6 result:
`[monitor] backend = file` with `log_file = ...` can show recent lines and `modelctl monitor router --follow` streams appended lines until interrupted.

Loop 7 result:
`[monitor] backend = systemd` with `service = ...` can show recent journal lines and `modelctl monitor router --follow` delegates to a `journalctl -u <service> -f` style read-only command.

Loop 8 result:
`modelctl tail 8080` is real when `[monitor.ports] 8080 = llama-cuda.service` is configured. It is read-only and reuses the systemd follow path.

Loop 9 result:
Monitor/discovery help no longer suggests unsupported `modelctl restart 8080`; restart is explicitly outside monitor's read-only scope.

Files changed across these loops:
- modelctl.py
- tests/test_storage_monitor.py
- tests/test_ux_delete_and_roadmap.py
- docs/backlog.md
- docs/phase-6-monitor-discovery.md
- README.md
- .agent/WORKLOOP.md

Out of scope preserved:
- broad process scanning
- service-name guessing
- router start/stop/restart behavior from monitor commands
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
Loop 10 — polish tail mapping docs/setup guidance.

Loop 10 recommended slice:
1. Inspect setup/doctor output for where `[monitor.ports]` guidance belongs.
2. Add only concise guidance/examples; do not auto-detect or write service mappings.
3. Keep monitor/tail read-only.
4. Add tests for any generated/help text changes.

Loop 10 acceptance criteria:
- users can discover the explicit `[monitor.ports]` mapping without reading source
- no config is mutated unless setup already writes user-requested config
- all examples point to implemented behavior
- all changes are committed and pushed

Blocker:
None for Loop 10 planning. Stay documentation/help focused unless a tiny tested code path is needed.

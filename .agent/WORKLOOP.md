# Current work loop

Objective:
Keep monitor work moving through small, committed, resumable loops with GitHub as source of truth.

Completed loops:
- Loop 6 — configured file-backend follow logs.
- Loop 7 — explicit systemd/journalctl-style monitor backend.
- Loop 8 — port-centric `tail` example reconciled with real configured behavior.
- Loop 9 — unsupported restart examples removed from monitor/read-only guidance.
- Loop 10 — tail mapping discovery added to setup/doctor guidance.
- Loop 11 — router systemd wrappers for logs/status/restart/reset-failed/start.

Loop 6 result:
`[monitor] backend = file` with `log_file = ...` can show recent lines and `modelctl monitor router --follow` streams appended lines until interrupted.

Loop 7 result:
`[monitor] backend = systemd` with `service = ...` can show recent journal lines and `modelctl monitor router --follow` delegates to a `journalctl -u <service> -f` style read-only command.

Loop 8 result:
`modelctl tail 8080` is real when `[monitor.ports] 8080 = llama-cuda.service` is configured. It is read-only and reuses the systemd follow path.

Loop 9 result:
Monitor/discovery help no longer suggests unsupported `modelctl restart 8080`; restart is explicitly outside monitor's read-only scope.

Loop 10 result:
`modelctl setup` and `modelctl doctor` now show the explicit `[monitor.ports] 8080 = llama-cuda.service` mapping needed for `modelctl tail 8080`; doctor also reports configured mappings without mutating config.

Loop 11 result:
`modelctl router` now wraps configured/default systemd service commands for the common local llama.cpp services: logs/status/command are read-oriented, while restart/reset-failed/start explicitly call the corresponding `sudo systemctl ... <service>` action.

Files changed across these loops:
- modelctl.py
- tests/test_storage_monitor.py
- tests/test_ux_delete_and_roadmap.py
- tests/test_cli_user_experience.py
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
Loop 12 — choose between richer monitor backends, recommendation/classification, or source metadata/downloads.

Loop 12 recommended slice:
1. Pick exactly one roadmap area and keep it bounded/test-first.
2. If extending router lifecycle further, require explicit configured metadata and tests; do not scan or guess arbitrary services/processes.
3. Keep docs/examples synchronized with implemented behavior.

Loop 12 acceptance criteria:
- only implemented commands are advertised
- tests cover every new command path
- GitHub/local/remote checkout are synced after commit/push

Blocker:
None. The router wrapper slice should be treated as complete once verification is green.

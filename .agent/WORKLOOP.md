# Current work loop

Objective:
Keep monitor work moving through small, committed, resumable loops with GitHub as source of truth.

Completed loops:
- Loop 6 — configured file-backend follow logs.
- Loop 7 — explicit systemd/journalctl-style monitor backend.
- Loop 8 — port-centric `tail` example reconciled with real configured behavior.
- Loop 9 — unsupported restart examples removed from monitor/read-only guidance.
- Loop 10 — tail mapping discovery added to setup/doctor guidance.

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
Loop 11 — read-only router status/command surface.

Loop 11 recommended slice:
1. Implement the smallest first-class `router` parser surface for read-only commands only: `modelctl router status` and `modelctl router command`.
2. `router status` should report configured router ini, endpoint/monitor metadata if present, and fail clearly when status cannot be determined; it must not restart/reload/kill anything.
3. `router command` should show configured launch guidance from modelctl-owned metadata where available; if metadata is missing, fail clearly and point to setup/doctor guidance.
4. Do not implement `router reload`, `router restart`, service guessing, process guessing, or broad discovery in this loop.
5. Add focused tests and update docs/backlog/requirements so files remain the source of truth.

Loop 11 acceptance criteria:
- `modelctl router status` and `modelctl router command` are discoverable in help
- both commands are read-only and backend/config driven
- unsupported/missing metadata fails clearly with actionable guidance
- no parser/help surface advertises implemented reload/restart behavior yet
- GitHub/local/remote checkout are synced after commit/push

Blocker:
None for Loop 11 planning. Keep router management separate from monitor/tail and implement read-only status/command before any reload/restart work.

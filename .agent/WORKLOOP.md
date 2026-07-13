# Current work loop

Objective:
Keep monitor work moving through small, committed, resumable loops with GitHub as source of truth.

Completed loops:
- Loop 6 — configured file-backend follow logs.
- Loop 7 — explicit systemd/journalctl-style monitor backend.
- Loop 8 — port-centric `tail` example reconciled with real configured behavior.

Loop 6 result:
`[monitor] backend = file` with `log_file = ...` can show recent lines and `modelctl monitor router --follow` streams appended lines until interrupted.

Loop 7 result:
`[monitor] backend = systemd` with `service = ...` can show recent journal lines and `modelctl monitor router --follow` delegates to a `journalctl -u <service> -f` style read-only command.

Loop 8 result:
`modelctl tail 8080` is real when `[monitor.ports] 8080 = llama-cuda.service` is configured. It is read-only and reuses the systemd follow path.

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
Loop 9 — reconcile restart examples with product safety rules.

Loop 9 recommended slice:
1. Inspect every `restart 8080` mention in README/help/docs/tests.
2. Decide whether to remove it from monitor examples or introduce a separate explicitly configured guarded command outside monitor.
3. Keep monitor read-only.
4. If adding any restart behavior, require explicit config, dry-run/confirmation safeguards, and targeted tests before implementation.
5. Prefer documentation/help correction if restart is not part of the current product slice.

Loop 9 acceptance criteria:
- monitor help no longer implies monitor commands restart services
- any remaining restart mention is clearly operator context or backed by implemented guarded behavior
- no broad service/process discovery is added
- all changes are committed and pushed

Blocker:
None for Loop 9 planning. The safest likely slice is help/docs correction, not service mutation.

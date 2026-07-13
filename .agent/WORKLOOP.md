# Current work loop

Objective:
Keep monitor work moving through small, committed, resumable loops with GitHub as source of truth.

Completed loop:
Loop 6 — configured file-backend follow logs.

Loop 6 scope:
- Add the first real configured monitor backend behavior after monitor discovery UX.
- Keep behavior read-only.
- Report backend details.
- Show recent configured log lines.
- Follow appended log lines for the configured file backend.

Files changed in Loop 6:
- modelctl.py
- tests/test_storage_monitor.py
- docs/backlog.md
- docs/phase-6-monitor-discovery.md
- README.md
- .agent/WORKLOOP.md

Out of scope for Loop 6:
- broad process scanning
- service-name guessing
- router start/stop/restart behavior
- archive / restore / delete / recover flows
- benchmark / recommend flows
- GPU/model-management changes

Decision:
The narrowest coherent backend was `[monitor] backend = file` with `log_file = ...`.
`modelctl monitor router --follow` now prints the current tail and streams appended lines from that file until interrupted. `--json --follow` fails clearly because JSON output is a snapshot envelope, not a stream.

Validation run for Loop 6:
- `python -m py_compile modelctl.py tests/test_storage_monitor.py`
- `python -m unittest tests.test_storage_monitor -v`

Next loop:
Loop 7 — explicit systemd/journalctl-style monitor backend.

Loop 7 recommended slice:
1. Add config-driven service log monitoring only; do not scan all processes.
2. Support a clear config shape such as:
   - `[monitor] backend = systemd`
   - `service = llama-cuda.service`
3. Make `modelctl monitor router --follow` produce behavior similar to:
   - `journalctl -u llama-cuda.service -f`
4. Keep it read-only.
5. Add tests that mock the subprocess call rather than requiring systemd in CI.
6. Preserve the existing file-backend behavior and JSON snapshot behavior.

Loop 7 acceptance criteria:
- systemd backend reports the configured service name.
- non-follow mode shows recent journal lines.
- follow mode delegates to an explicit `journalctl -u <service> -f`-style command.
- missing `service` fails clearly.
- unsupported JSON follow behavior is clear and tested.
- no broad service/process discovery is added.

Blocker:
None for Loop 7 planning. The implementation should stay narrow and configured-only.

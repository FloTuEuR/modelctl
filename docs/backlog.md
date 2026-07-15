# modelctl Implementation Backlog

This file tracks small product amendments discovered during development.

The source of truth remains:
- docs/requirements.md
- docs/roadmap.md
- docs/safety.md
- docs/settings-rules.md
- docs/archive-restore-delete-recover.md

Backlog items should be small, testable, and suitable for iterative agent work.

---

## Queued Amendments

### B-001 - Monitor discovery follow-up

Status: partially completed
Phase: monitor follow-up
Scope: medium

Implemented in commit babf09f:
- `modelctl monitor discover`
- `modelctl monitor discover --json`
- Read-only endpoint discovery for configured endpoints and common local
  OpenAI-compatible endpoints.
- Structured JSON candidate output with `mutated: false`.
- Tests for no reachable endpoint, one reachable endpoint, multiple reachable
  endpoints, JSON envelope shape, and preservation of existing `monitor router`
  behavior.

Additional completed follow-up:
- `monitor router` with no configured backend now suggests `modelctl monitor discover` in human output.
- JSON output for the unconfigured monitor path includes `suggested_commands` and `next_steps`.

Completed in Loop 6:
- `[monitor] backend = file` can show recent configured log lines.
- `modelctl monitor router --follow` streams appended lines from the configured
  file backend without mutating router/server/config state.
- `--json --follow` fails clearly because JSON output is snapshot-oriented.

Completed in Loop 7:
- `[monitor] backend = systemd` with `service = ...` can show recent journal
  lines via an explicit configured service.
- `modelctl monitor router --follow` delegates to a `journalctl -u <service> -f`
  style command without broad process/service discovery.
- `--json --follow` fails clearly because JSON output is snapshot-oriented.

Completed in Loop 8:
- `modelctl tail 8080` is now backed by explicit `[monitor.ports]` service
  mapping instead of being a stale help-only example.
- Tail remains read-only and reuses the configured systemd backend behavior.

Completed in Loop 9:
- Removed unsupported `modelctl restart 8080` from monitor/read-only examples.
- Discovery now says restart is not a monitor command instead of suggesting an
  unimplemented modelctl restart path.

Remaining future work:
- Decide whether safe process-list discovery is worth adding.
- If process-list discovery is added, it must remain read-only and must not guess
  service names, log paths, or persistent endpoint selections.
- Tail mapping setup/doctor guidance is complete; router systemd wrappers now cover logs/status/restart/reset-failed/start for configured services.

Acceptance criteria for the remaining follow-up:
- If process-list discovery is ever added, tests cover none, one, and multiple
  mocked process candidates.
- Discovery remains read-only.
- File backend shows which backend is in use.
- File backend can show recent logs.
- File backend can follow appended log lines.
- Systemd backend covers explicit configured service logs without broad process
  scanning.
- Tail examples are reconciled with real explicit mapping behavior.
- Restart examples are reconciled with monitor read-only safety rules.
- Next slice should avoid expanding router lifecycle further unless the action is explicitly configured and tested.

---

### B-002 - Missing required arguments should show command help

Status: completed (Slice 3)
Phase: CLI UX follow-up
Scope: small

Implemented in commit b40e7f8:
- `update-check` with no target now shows usage help instead of traceback.
- `show` and `benchmark` already delegate missing-target errors to argparse, which prints usage and exits 2.
- Tests added for update-check, show, and benchmark missing targets.

---

### B-003 - Add list filters for active/archive/enabled/disabled

Status: completed (Slice 2)
Phase: list command follow-up
Scope: small

Implemented in commit 11f1a7c:
- `--active` filters to models with location == "active"
- `--archived` filters to models with location == "archived"
- `--enabled` filters to aliases with enabled == True
- `--disabled` filters to aliases with enabled == False
- `--active --archived` and `--enabled --disabled` are invalid and fail with clear message
- JSON output includes `filters_applied` key
- Human output respects filters
- Tests cover all filter modes and JSON metadata

Potential future extension:
- `--location active|archive|missing|all` could replace `--active`/`--archived`
- `--alias-state enabled|disabled|all` could replace `--enabled`/`--disabled`


### B-004 - Router systemd service wrappers

Status: completed
Phase: router management
Scope: medium

Implemented:
- `modelctl router logs TARGET --follow` wraps `journalctl -u <service> -f`.
- `modelctl router restart TARGET` wraps `sudo systemctl restart <service>`.
- `modelctl router reset-failed TARGET` wraps `sudo systemctl reset-failed <service>`.
- `modelctl router start TARGET` wraps `sudo systemctl start <service>`.
- `modelctl router status`, `router command`, and `router services` expose read-only status/metadata.
- Targets resolve from `[router.services]`, `[monitor.ports]`, and built-in cuda/vulkan/cpu defaults.
- Tests cover help, JSON metadata, lifecycle command wrapping, and unknown-target failures.

Future work:
- Add more lifecycle actions only when backed by explicit configured metadata and tests.
- Keep monitor read-only; lifecycle actions stay under router.

---

## Related operational references

- Stable JSON output: `docs/json-output.md`
- Release readiness checklist: `docs/release-checklist.md`
- Monitor discovery usage and safety: `docs/phase-6-monitor-discovery.md`

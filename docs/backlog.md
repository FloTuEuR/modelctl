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

Remaining future work:
- Decide whether safe process-list discovery is worth adding.
- If process-list discovery is added, it must remain read-only and must not guess
  service names, log paths, or persistent endpoint selections.
- Next loop: add one configured monitoring backend that satisfies Phase 5 of
  `docs/roadmap.md` and the monitoring acceptance criteria in
  `docs/requirements.md`.
- Preferred next slice: wire a configured backend for real recent-log and
  follow-log output, keep it read-only, report the backend in human and JSON
  output, and add targeted tests before broader validation.

Acceptance criteria for the remaining follow-up:
- If process-list discovery is ever added, tests cover none, one, and multiple
  mocked process candidates.
- Discovery remains read-only.
- The next monitoring-backend slice shows which backend is in use.
- The next monitoring-backend slice can show recent logs.
- The next monitoring-backend slice can follow logs where the configured
  backend supports it.

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



## Related operational references

- Stable JSON output: `docs/json-output.md`
- Release readiness checklist: `docs/release-checklist.md`
- Monitor discovery usage and safety: `docs/phase-6-monitor-discovery.md`

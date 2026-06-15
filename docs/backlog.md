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

### B-001 - Monitor should discover running llama.cpp servers

Status: queued
Phase: monitor follow-up
Scope: medium

Problem:
`modelctl monitor` currently relies on configured monitor metadata. It should become more helpful when no monitor backend is configured.

Desired behaviour:
- Detect whether one or more `llama.cpp` / `llama-server` processes are running.
- If exactly one running server is found, report it as the likely router/server target where safe. Do not ask for additional server details.
- If more than one running server is found, present the candidates and require explicit selection or configuration. Do not pick blindly.
- If none are found, do not ask for server log details. Instead, explain how to configure file/systemd/docker monitoring.
- Do not guess unsafe service names or log paths.
- Do not mutate anything during monitor discovery.
- JSON output should expose discovery results in structured form.
- All discovery is read-only.

Acceptance criteria:
- `modelctl monitor router` with no configured backend returns a helpful discovery/configuration response.
- If one server is found, it is reported as the likely target without prompting for details.
- If none are found, the response explains how to configure monitoring without asking for server/log details.
- If multiple candidates are found, the response lists them and does not choose blindly.
- Discovery is read-only.
- Tests cover none, one, and multiple discovered candidates.

Suggested tests:
- monitor no backend and no running server
- monitor no backend and one mocked llama-server process
- monitor no backend and multiple mocked llama-server processes
- monitor JSON discovery output

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

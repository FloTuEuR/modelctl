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
- If exactly one running server is found, use that as the likely router/server target where safe.
- If more than one running server is found, present the candidates and ask the user to select/configure one.
- If none are found, ask the user to provide monitor details such as log file path, backend type, service name, or container name.
- Do not guess unsafe service names or log paths.
- Do not mutate anything during monitor discovery.
- JSON output should expose discovery results in structured form.

Acceptance criteria:
- `modelctl monitor router` with no configured backend returns a helpful discovery/configuration response.
- If no running server is found, the response explains how to configure file/systemd/docker monitoring.
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

Status: queued
Phase: CLI UX follow-up
Scope: small

Problem:
Some commands, such as `update-check`, return raw errors when required arguments are missing. The CLI should be more helpful.

Desired behaviour:
- If a required command argument is missing, show the relevant command help/usage.
- Exit with a non-zero code.
- Human output should be helpful.
- JSON mode should return the standard error envelope where supported:
  - status: error
  - command: command name
  - data: {}
  - warnings: []
  - error: { code, message, usage/help where practical }

Acceptance criteria:
- Missing-argument cases do not produce confusing tracebacks or raw errors.
- `modelctl update-check` without target shows command-specific help.
- Similar commands follow the same pattern where practical.
- Tests cover at least `update-check`, and one lifecycle/inspect command if applicable.

Suggested tests:
- update-check missing target
- show missing target
- benchmark missing target if currently applicable
- JSON missing argument error where JSON is supported

---

### B-003 - Add list filters for active/archive/enabled/disabled

Status: queued
Phase: list command follow-up
Scope: small

Problem:
`modelctl list` should allow users and agents to filter results instead of parsing all output.

Desired behaviour:
Add filters such as:
- `modelctl list --active`
- `modelctl list --archived`
- `modelctl list --enabled`
- `modelctl list --disabled`

Potential additional structured option:
- `modelctl list --location active|archive|missing|all`
- `modelctl list --alias-state enabled|disabled|all`

Keep aliases simple for humans and structured flags useful for agents.

Acceptance criteria:
- Human output respects filters.
- `list --json` includes filters applied under the JSON envelope.
- Filters can be combined where sensible.
- Invalid filter combinations fail clearly.
- Tests cover active, archived, enabled, disabled, and JSON filter metadata.

Suggested tests:
- list active only
- list archived only
- list enabled aliases only
- list disabled aliases only
- list --json includes filters_applied
- invalid filter combination if any are mutually exclusive


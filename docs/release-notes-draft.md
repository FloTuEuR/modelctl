# Release Notes Draft

This draft summarizes the current `work/modelctl-router-lifecycle` branch for a
future GitHub release or README announcement.

## Highlights

- Aligned lifecycle commands around archive, restore, delete, and recover.
- Replaced rollback-oriented language with archive/restore/delete/recover
  lifecycle terminology.
- Added `add` as the preferred command while keeping `add-entry` as a temporary
  compatibility alias.
- Made archive preserve aliases by default, with explicit options for disabling
  aliases when needed.
- Added restore support for moving archived models back to active storage.
- Added focused delete recovery manifests and recover support for affected
  aliases/sections.
- Centralized generated modelctl artifacts under modelctl-owned config, data,
  state, and cache directories.
- Stabilized JSON output envelopes for automation and dashboards.
- Added JSON output for inspect commands, dry-run lifecycle planning, safe
  applied lifecycle operations, and monitor metadata.
- Added list filters for active, archived, enabled, and disabled model/alias
  views.
- Improved missing-argument help for common CLI UX paths.
- Added read-only monitor log abstraction and read-only endpoint discovery.

## JSON and automation

Commands that support JSON use a stable envelope:

```json
{
  "status": "ok",
  "command": "list",
  "data": {},
  "warnings": [],
  "error": null
}
```

See `docs/json-output.md` for examples and command coverage.

## Monitor discovery

`modelctl monitor discover` helps identify local OpenAI-compatible
`llama.cpp` endpoints without mutating configuration or selecting a permanent
server. It reports no, one, or multiple reachable candidates and supports JSON
output for automation.

See `docs/phase-6-monitor-discovery.md` for details.

## Safety and readiness

The branch has focused tests for archive/restore/delete/recover flows, JSON
schema behavior, list filters, storage hygiene, monitor log output, and monitor
discovery. Before release, run the release checklist in
`docs/release-checklist.md`.

## Known limitations

- Destructive delete remains intentionally guarded and requires explicit apply or
  confirmation semantics.
- Process-list monitor discovery is not implemented in this version.
- Monitor discovery performs endpoint checks only and does not configure a
  permanent endpoint.
- Some roadmap items remain future work, especially deeper router setup and
  monitoring backends.

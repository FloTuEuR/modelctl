# Release Notes Draft

Public-facing draft for the current `work/modelctl-router-lifecycle` branch.
Use this as a starting point for a future GitHub release or pull-request
summary after human review.

## Summary

This branch turns modelctl into a safer and more automation-friendly CLI for
managing `llama.cpp` router presets, aliases, GGUF model files, lifecycle
metadata, and read-only monitoring information.

## User-facing changes

### Lifecycle command alignment

- Standardized lifecycle language around archive, restore, delete, and recover.
- Kept `add-entry` as a temporary compatibility alias while making `add` the
  preferred command.
- Removed rollback as a normal lifecycle concept in favor of explicit
  archive/restore/delete/recover operations.

### Archive and restore

- Archive now preserves aliases by default.
- Archive supports dry-run planning and applied JSON output.
- Restore moves archived models back to active storage and supports dry-run and
  safe applied JSON output.
- Archive metadata is stored under modelctl-owned state paths unless the user
  explicitly configures otherwise.

### Delete and recover safety model

- Delete remains intentionally guarded.
- Delete dry-run JSON describes affected model files, aliases, sections, and the
  planned recovery manifest without performing destructive changes.
- Applied delete continues to require explicit apply/confirmation semantics.
- Recover uses focused delete recovery manifests to restore affected
  alias/section configuration without overwriting unrelated router edits.

### JSON output and automation

- Added a stable JSON envelope for automation:

  ```json
  {
    "status": "ok",
    "command": "list",
    "data": {},
    "warnings": [],
    "error": null
  }
  ```

- Added JSON coverage for inspect commands, list filters, dry-run lifecycle
  planning, safe applied lifecycle operations, monitor log metadata, and monitor
  discovery.
- See `docs/json-output.md` for examples and command coverage.

### List filters

- Added `modelctl list --active` and `modelctl list --archived`.
- Added `modelctl list --enabled` and `modelctl list --disabled`.
- JSON list output now includes `filters_applied` metadata.

### Monitor discovery

- Added `modelctl monitor discover` and `modelctl monitor discover --json`.
- Discovery checks configured endpoints and common local OpenAI-compatible
  endpoints using read-only model-listing requests.
- Discovery reports no, one, or multiple reachable candidates without mutating
  configuration or making a permanent selection.
- See `docs/phase-6-monitor-discovery.md` for usage and safety details.

### CLI UX and storage hygiene

- Improved missing-argument help for common commands.
- Centralized generated artifacts under modelctl-owned config, data, state, and
  cache directories.
- Added release-readiness and JSON-output documentation.

## Testing status

Current branch validation uses:

```bash
uv run --no-project --with pytest python -m pytest tests -q
git diff --check
```

The latest release-readiness pass should be recorded in
`docs/release-readiness-report.md` before tagging or opening a release PR.

## Known limitations

- Destructive delete remains intentionally guarded and is not a casual JSON apply
  path.
- Monitor discovery is endpoint-based only; process-list discovery is not
  implemented in this version.
- Monitor discovery does not write config or select a permanent endpoint.
- Deeper router setup and monitoring backend configuration remain roadmap items.

## Upgrade and usage notes

- Existing users of `add-entry` should migrate to `add` when convenient.
- Review `docs/safety.md` before running mutating commands.
- Use `--dry-run` and `--json` where available for automation previews.
- Run the release checklist before tagging or publishing a release.

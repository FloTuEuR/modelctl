# JSON Output Envelopes

This document describes the stable JSON output behavior for `modelctl` CLI commands.

## Success Envelope

All successful commands return valid JSON with the following structure:

```json
{
  "status": "ok",
  "command": "<command_name>",
  "data": {
    // Command-specific data
  },
  "warnings": [],
  "error": null
}
```

### Fields

- `status`: Always `"ok"` for successful execution
- `command`: The command that was executed (e.g., `"list"`, `"add"`, `"delete"`)
- `data`: Command-specific payload
- `warnings`: List of non-blocking warnings (empty if none)
- `error`: `null` for success, or error details for failures

## Error Envelope

For failed commands:

```json
{
  "status": "error",
  "command": "<command_name>",
  "data": null,
  "warnings": [],
  "error": {
    "code": "<error_code>",
    "message": "Human-readable error message",
    "details": {
      // Optional structured details
    }
  }
}
```

## Command-Specific JSON Shapes

### `list --json`

```json
{
  "status": "ok",
  "command": "list",
  "data": {
    "models": [
      {
        "id": "model_id",
        "name": "model name",
        "path": "/models/example.gguf",
        "sha256": "..."
      }
    ],
    "filters_applied": {}
  },
  "warnings": [],
  "error": null
}
```

- `filters_applied`: Object containing any filter criteria (e.g., `{"status": "active"}`)

### `show <model_id> --json`

```json
{
  "status": "ok",
  "command": "show",
  "data": {
    "id": "model_id",
    "name": "model name",
    "path": "/models/example.gguf",
    "sha256": "..."
  },
  "warnings": [],
  "error": null
}
```

### `add <model_id> --json`

```json
{
  "status": "ok",
  "command": "add",
  "data": {
    "id": "model_id",
    "path": "/models/example.gguf",
    "status": "active"
  },
  "warnings": [],
  "error": null
}
```

### `archive <model_id> --json`

```json
{
  "status": "ok",
  "command": "archive",
  "data": {
    "id": "model_id",
    "archived_path": "/archive/example.gguf",
    "status": "archived"
  },
  "warnings": [],
  "error": null
}
```

### `restore <model_id> --json`

```json
{
  "status": "ok",
  "command": "restore",
  "data": {
    "id": "model_id",
    "restored_path": "/models/example.gguf",
    "status": "active"
  },
  "warnings": [],
  "error": null
}
```

### `delete <model_id> --json`

```json
{
  "status": "ok",
  "command": "delete",
  "data": {
    "id": "model_id",
    "deleted": true
  },
  "warnings": [],
  "error": null
}
```

### `recover <model_id> --json`

```json
{
  "status": "ok",
  "command": "recover",
  "data": {
    "id": "model_id",
    "recovered_path": "/models/example.gguf",
    "status": "active"
  },
  "warnings": [],
  "error": null
}
```

### `--dry-run` with JSON

All commands support `--dry-run` flag. When combined with `--json`:

```json
{
  "status": "ok",
  "command": "archive",
  "data": {
    "dry_run": true,
    "would_archive_path": "/archive/example.gguf",
    "status": "archived"
  },
  "warnings": [],
  "error": null
}
```

## Warnings Array

Warnings are non-blocking informational messages:

- Path already exists (archive/restore)
- Model not found
- Permissions warning
- Deprecated options used

## Error Object

```json
{
  "code": "<error_code>",
  "message": "Human-readable error message",
  "details": {
    // Optional structured details
  }
}
```

## Safe Lifecycle Examples

### Archive (Safe)

```bash
modelctl archive <model_id> --json --dry-run
```

Response:
```json
{
  "status": "ok",
  "command": "archive",
  "data": {
    "dry_run": true,
    "would_archive_path": "/archive/example.gguf",
    "status": "archived"
  },
  "warnings": [],
  "error": null
}
```

### Restore (Safe)

```bash
modelctl restore <model_id> --json --dry-run
```

Response:
```json
{
  "status": "ok",
  "command": "restore",
  "data": {
    "dry_run": true,
    "would_restore_path": "/models/example.gguf",
    "status": "active"
  },
  "warnings": [],
  "error": null
}
```

### Delete (Destructive - Guarded)

Delete operations require interactive confirmation unless `--dry-run` is used.

```bash
modelctl delete <model_id> --json --dry-run
```

Response:
```json
{
  "status": "ok",
  "command": "delete",
  "data": {
    "dry_run": true,
    "would_delete": true,
    "id": "model_id"
  },
  "warnings": [],
  "error": null
}
```

## Notes

- JSON output is a separate mode from human-readable output
- Use `--json` flag to enable JSON mode
- JSON is always valid and parseable
- Empty arrays `[]` and null values `null` are valid
- Paths use generic placeholders (`/models/example.gguf`, `/archive/example.gguf`)

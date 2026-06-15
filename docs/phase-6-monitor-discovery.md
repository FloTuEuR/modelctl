# Monitor Discovery

`modelctl monitor discover` is a read-only helper for finding local
OpenAI-compatible `llama.cpp` router/server endpoints before configuring deeper
monitoring.

## Commands

```bash
modelctl monitor discover
modelctl monitor discover --json
```

Discovery is intentionally conservative. It never writes configuration, starts or
stops services, kills processes, or stores a permanent endpoint selection.

## What discovery checks

The first version checks endpoint URLs only:

1. Explicit monitor settings in the modelctl config, when present:
   - `[monitor] endpoint = ...`
   - `[monitor] base_url = ...`
   - `[monitor] url = ...`
   - `[monitor] endpoints = ...`
2. Common local OpenAI-compatible `llama.cpp` endpoints:
   - `http://127.0.0.1:8080/v1`
   - `http://localhost:8080/v1`

For each candidate, modelctl performs a short-timeout read-only request to the
models endpoint and records whether it was reachable.

## Human output

When no server is found, output says no endpoint was reachable and suggests
providing endpoint or log details.

When one server is found, output marks that endpoint as selected/recommended for
this run only. No config is written.

When multiple servers are found, output lists them and says explicit
selection/configuration is required. modelctl does not guess a permanent choice.

Example:

```text
Monitor discovery (read-only)
  no mutation performed
  found count: 1
  selected/recommended: http://127.0.0.1:8080/v1
  - endpoint: http://127.0.0.1:8080/v1
    source: default_loopback
    reachable: true
    models endpoint: http://127.0.0.1:8080/v1/models
    model ids: example-model
```

## JSON output

`--json` uses the standard modelctl envelope:

```json
{
  "status": "ok",
  "command": "monitor discover",
  "data": {
    "candidates": [
      {
        "endpoint": "http://127.0.0.1:8080/v1",
        "reachable": true,
        "models_endpoint": "http://127.0.0.1:8080/v1/models",
        "model_ids": ["example-model"],
        "error_message": null,
        "source": "default_loopback"
      }
    ],
    "found_count": 1,
    "selected": "http://127.0.0.1:8080/v1",
    "mutated": false
  },
  "warnings": [],
  "error": null
}
```

Candidate fields:

- `endpoint` - probed base endpoint.
- `reachable` - whether the model listing request succeeded.
- `models_endpoint` - exact URL queried for model IDs.
- `model_ids` - discovered model IDs, if available.
- `error_message` - connection, timeout, HTTP, or JSON parsing error text.
- `source` - `configured`, `default_loopback`, or `default_localhost`.

## Safety guarantees

- Read-only endpoint checks only.
- No config mutation.
- No service lifecycle operations.
- No process killing.
- No permanent endpoint selection.
- Multiple reachable endpoints require explicit user configuration.

## Limitations

- Process-list discovery is intentionally not implemented in this version.
- Only endpoint/model-listing checks are used.
- Configured endpoints are trusted as user-provided local operational inputs.
- A reachable endpoint can still be unsuitable for a given workflow; use the
  listed model IDs and explicit configuration to decide.

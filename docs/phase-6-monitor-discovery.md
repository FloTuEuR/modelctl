# Monitor Discovery

`modelctl monitor` helps you find and inspect local llama servers without changing
anything.

## Common commands

```bash
modelctl monitor
modelctl monitor discover
modelctl monitor 8080
modelctl monitor 8082
modelctl tail 8080
modelctl restart 8080
modelctl monitor discover --json
```

Ports identify local llama servers. Discovery is intentionally conservative. It
never writes configuration, starts or stops services, kills processes, or stores
permanent endpoint selections.

## What discovery checks

The current implementation checks local endpoint URLs only:

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

Default human output is concise. For each discovered server it shows:

- port
- endpoint
- reachable status
- mapped service, if known
- `current model`
- `available models`

Rules for `current model`:

- If exactly one model is exposed by `/v1/models`, modelctl shows that model as
  the current served model.
- If multiple models are exposed and no better local signal identifies the
  active one, modelctl reports `current model: unknown`.
- Human output does **not** dump the full model ID list by default.
- JSON output keeps the full `model_ids` list for automation.

Example:

```text
Monitor discovery (read-only)
found count: 2

8080  reachable  http://127.0.0.1:8080/v1
service: unknown
current model: unknown
available models: 8

8082  reachable  http://127.0.0.1:8082/v1
service: unknown
current model: qwen-mini
available models: 1

Try:
modelctl monitor 8080
modelctl monitor 8082
modelctl tail 8080
modelctl restart 8080
modelctl tail 8082
modelctl restart 8082
```


## Configured file backend

For a known local log file, configure:

```ini
[monitor]
backend = file
log_file = /path/to/router.log
```

Then use:

```bash
modelctl monitor router --lines 50
modelctl monitor router --follow
```

The file backend is read-only. `--follow` prints the current tail, then streams
new lines appended to the configured file until interrupted. JSON output remains
for snapshots only; `--json --follow` fails clearly instead of producing an
ambiguous streaming envelope.

## Configured systemd backend

For a known systemd service, configure:

```ini
[monitor]
backend = systemd
service = llama-cuda.service
```

Then use:

```bash
modelctl monitor router --lines 50
modelctl monitor router --follow
```

The systemd backend is explicit and read-only. It does not discover, start, stop,
or restart services. Follow mode delegates to a `journalctl -u <service> -f`
style command for the configured service.

## JSON output

`--json` uses the standard modelctl envelope. Each candidate keeps the full
machine-readable fields, including:

- `endpoint`
- `port`
- `reachable`
- `models_endpoint`
- `model_ids`
- `available_model_count`
- `current_model`
- `service`
- `error_message`
- `source`

## Safety guarantees

- Read-only endpoint checks only.
- No config mutation.
- No service lifecycle operations.
- No process killing.
- No permanent endpoint selection.
- Multiple reachable endpoints do not cause modelctl to invent a current model.

## Limitations

- Process-list discovery is intentionally not implemented in this version.
- Service mapping currently reports `unknown` unless separate metadata is added.
- Current-model detection uses safe local endpoint evidence only.
- A reachable endpoint can still be unsuitable for a given workflow; use
  explicit configuration when you need stronger guarantees.

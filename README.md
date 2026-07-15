# llama-modelctl

Safe-by-default CLI for inspecting and managing local `llama.cpp` router model preset files.

`llama-modelctl` imports an existing router `models.ini`/preset, lists aliases and GGUF files, previews risky actions, archives models with recovery metadata, and avoids destructive changes unless explicitly confirmed.

## Status

Early public-ready prototype. Archive and delete paths are intentionally conservative.

## Requirements

- Python 3.10+
- A `llama.cpp` router-style ini/preset file containing sections with `model = /path/to/file.gguf`

No third-party Python dependencies are required for the core CLI.

## Quick start

```bash
git clone https://github.com/FloTuEuR/modelctl.git
cd modelctl
python3 modelctl.py setup
python3 modelctl.py doctor
python3 modelctl.py list
```

Or use the portable launcher from a checkout:

```bash
./modelctl setup
./modelctl list
```

## Safe archive workflow

Apply directly:

```bash
modelctl archive 1
modelctl archive alias:my-model
modelctl archive path:/path/to/model.gguf
```

Preview without mutating anything:

```bash
modelctl archive 1 --dry-run
```

The archive command:

- applies by default;
- accepts `--dry-run` when you want a smoke-test preview first;
- creates an ini backup next to the router preset;
- comments impacted aliases instead of deleting them;
- writes a recovery plan JSON under the configured modelctl plans directory unless `--plan` is provided.

## Safety notes

Read [`docs/safety.md`](docs/safety.md) before using mutating commands. For automation output, see [`docs/json-output.md`](docs/json-output.md). For release checks, see [`docs/release-checklist.md`](docs/release-checklist.md).

Important defaults:

- `setup`, `import`, `list`, `show`, `aliases`, and `doctor` do not modify your router ini.
- `delete --dry-run` is an impact preview only; `delete TARGET` requires an interactive terminal and typed confirmation.
- `archive`, `restore`, `recover`, `enable`, `disable`, `add`, and `scan` are routine operations; use `--dry-run` where available when you want an impact preview instead.
- `add-entry` is a temporary deprecated compatibility alias for `add`.
- `benchmark` is not a dry-run command: it tries to run a real `llama-bench` invocation immediately and fails clearly if `llama-bench` is unavailable.
- Recovery plan JSON files contain local paths and should be treated as local operational metadata.

## Monitor discovery

Use monitor discovery when you want to find local llama servers quickly:

```bash
modelctl monitor
modelctl monitor discover
modelctl monitor 8080
modelctl monitor 8082
modelctl tail 8080
```

Monitor and tail commands are read-only; service restarts are intentionally not part of this monitor slice.

`modelctl monitor discover` stays read-only. It reports each discovered server, shows the current model when it can be determined safely, and otherwise reports `current model: unknown`. JSON output keeps the full model ID list for automation. With `[monitor] backend = file` and `log_file = ...`, `modelctl monitor router --follow` prints the current tail and streams appended log lines without mutating router/server state. With `[monitor] backend = systemd` and `service = llama-cuda.service`, it delegates to a journalctl-style read-only service log follow. `modelctl tail 8080` is real when `[monitor.ports] 8080 = llama-cuda.service` is configured. See [`docs/phase-6-monitor-discovery.md`](docs/phase-6-monitor-discovery.md).

## Router service wrappers

Use router wrappers for the common local llama.cpp systemd services so you do not need to remember raw commands:

```bash
modelctl router logs cuda --follow
modelctl router logs vulkan --follow
modelctl router logs cpu --follow
modelctl router restart cuda
modelctl router reset-failed cuda
modelctl router start cuda
```

These map to configured/default systemd services such as `llama-cuda.service`, `llama-vulkan.service`, and `llama-cpu.service`. See [`docs/router-configuration.md`](docs/router-configuration.md).

## Roadmap and recommendation rules

Model acquisition and tuning features are still only partially implemented in v0.1. See [`docs/roadmap.md`](docs/roadmap.md) for what is still planned versus what now works.

Today:

- `benchmark TARGET` runs a real `llama-bench` invocation when available and persists results for later display in `show`.
- `update-check TARGET` can persist Hugging Face freshness state when source repo/file metadata is known.
- `enable` / `disable` apply real ini edits by default, with `--dry-run` available for preview.
- `add` appends a real ini entry by default, with `--dry-run` available for preview.

See [`docs/settings-rules.md`](docs/settings-rules.md) for the current recommendation/output targets: 20+ t/s, 65.5k good context, 128k+ ideal context, full VRAM fit, quality, and large-JSON robustness.

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

## License

MIT. See [`LICENSE`](LICENSE).

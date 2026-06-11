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

Read [`docs/safety.md`](docs/safety.md) before using mutating commands.

Important defaults:

- `setup`, `import`, `list`, `show`, `aliases`, and `doctor` do not modify your router ini.
- `delete --dry-run` is an impact preview only; `delete TARGET` requires an interactive terminal and typed confirmation.
- `archive`, `enable`, `disable`, `add-entry`, and `scan` apply real changes by default; use `--dry-run` when you want an impact preview instead.
- `benchmark` is not a dry-run command: it tries to run a real `llama-bench` invocation immediately and fails clearly if `llama-bench` is unavailable.
- Recovery plan JSON files contain local paths and should be treated as local operational metadata.

## Roadmap and recommendation rules

Model acquisition and tuning features are still only partially implemented in v0.1. See [`docs/roadmap.md`](docs/roadmap.md) for what is still planned versus what now works.

Today:

- `benchmark TARGET` runs a real `llama-bench` invocation when available and persists results for later display in `show`.
- `update-check TARGET` can persist Hugging Face freshness state when source repo/file metadata is known.
- `enable` / `disable` apply real ini edits by default, with `--dry-run` available for preview.
- `add-entry` now appends a real ini entry by default, with `--dry-run` available for preview.

See [`docs/settings-rules.md`](docs/settings-rules.md) for the current recommendation/output targets: 20+ t/s, 65.5k good context, 128k+ ideal context, full VRAM fit, quality, and large-JSON robustness.

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
```

## License

MIT. See [`LICENSE`](LICENSE).

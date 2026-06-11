# llama-modelctl

Safe-by-default CLI for inspecting and managing local `llama.cpp` router model preset files.

`llama-modelctl` imports an existing router `models.ini`/preset, lists aliases and GGUF files, previews risky actions, archives models with rollback metadata, and avoids destructive changes unless explicitly confirmed.

## Status

Early public-ready prototype. Mutating archive and delete paths are intentionally conservative and require explicit human approval.

## Requirements

- Python 3.10+
- A `llama.cpp` router-style ini/preset file containing sections with `model = /path/to/file.gguf`

No third-party Python dependencies are required for the core CLI.

## Quick start

```bash
git clone https://github.com/YOUR-USER/llama-modelctl.git
cd llama-modelctl
python3 modelctl.py setup /path/to/models.ini --yes
python3 modelctl.py doctor
python3 modelctl.py list
```

Or use the portable launcher from a checkout:

```bash
./modelctl setup /path/to/models.ini --yes
./modelctl list
```

## Safe archive workflow

Preview first:

```bash
modelctl archive model:1
modelctl archive alias:my-model
modelctl archive path:/path/to/model.gguf
```

Apply only after reviewing the preview:

```bash
modelctl archive model:1 --yes
```

The archive command:

- is dry-run by default;
- requires `--yes` before moving files or editing the ini;
- creates an ini backup next to the router preset;
- comments impacted aliases instead of deleting them;
- writes a rollback plan JSON under the configured modelctl plans directory unless `--plan` is provided.

Rollback is also dry-run by default:

```bash
modelctl rollback ~/.config/modelctl/plans/archive-YYYYMMDDTHHMMSSZ.json
modelctl rollback ~/.config/modelctl/plans/archive-YYYYMMDDTHHMMSSZ.json --yes
```

## Safety notes

Read [`docs/safety.md`](docs/safety.md) before using mutating commands.

Important defaults:

- `setup`, `import`, `list`, `show`, `aliases`, and `doctor` do not modify your router ini.
- `delete --dry-run` is an impact preview only; `delete TARGET` requires an interactive terminal and typed confirmation.
- `archive`, `rollback`, `enable`, `disable`, `add-entry`, and `scan` are dry-run by default and require `--yes` to write changes.
- `benchmark` is not a dry-run command: it tries to run a real `llama-bench` invocation immediately and fails clearly if `llama-bench` is unavailable.
- rollback plans contain local paths and should be treated as local operational metadata.

## Roadmap and recommendation rules

Model acquisition and tuning features are planned but not fully implemented in v0.1. See [`docs/roadmap.md`](docs/roadmap.md) for the intended Hugging Face download, up-to-date check, benchmark, suggest settings, and hardware/config detection workflows.

The current CLI exposes the command surfaces for `update-check`, `benchmark`, `add-entry`, `enable`, `disable`, and `rules` so the UX is visible before the full implementations are added. See [`docs/settings-rules.md`](docs/settings-rules.md) for the default outcomes: 20+ t/s, 65.5k good context, 128k+ ideal context, full VRAM fit, quality, and large-JSON robustness.

## Development

Run tests:

```bash
python -m unittest discover -s tests -v
python scripts/check_private_markers.py
```

## License

MIT. See [`LICENSE`](LICENSE).

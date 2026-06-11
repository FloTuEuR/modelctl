# Safety model

`llama-modelctl` is designed for local GGUF model inventories where mistakes can be expensive: a wrong move can break a running router, waste large disk copies, or remove a model that another service depends on.

## Read-only commands

These commands are read-only with respect to the router ini and model files:

- `setup`
- `import`
- `doctor`
- `list`
- `show`
- `aliases`
- `delete --dry-run`
- `archive --dry-run`
- `enable --dry-run`
- `disable --dry-run`
- `add-entry --dry-run`
- `scan --dry-run`

## Mutating commands

Only these paths intentionally mutate files:

- `setup`: writes modelctl's own config and registry only; it does not edit the router ini.
- `delete TARGET`: requires an interactive terminal and typed confirmation; removes impacted alias sections and permanently deletes the selected model file.
- `archive ...`: edits the router ini, writes an ini backup, moves model files, and writes recovery metadata unless `--dry-run` is used.
- `enable TARGET`: edits the router ini to uncomment/restore an alias section unless `--dry-run` is used.
- `disable TARGET`: edits the router ini to comment out an alias section unless `--dry-run` is used.
- `add-entry`: appends a generated ini entry unless `--dry-run` is used.
- `scan`: appends newly discovered disabled entries unless `--dry-run` is used.

## Delete safeguards

Delete apply currently requires:

- an interactive TTY; non-interactive stdin is refused;
- typed confirmation matching the selected model filename;
- a router ini backup;
- atomic text writes for ini and backup files;
- `--dry-run` for agents/scripts that need to inspect impact without mutation.

## Archive safeguards

Archive apply currently requires:

- existing source files;
- non-existing destinations;
- a router ini backup;
- recovery metadata;
- atomic text writes for ini, backup, and plan files;
- backup hash verification when available.

## Operational cautions

- Stop or reload your router after changing aliases if clients need the live `/v1/models` catalogue to reflect the new ini.
- Review archive destinations before applying. Archive folder naming uses filename heuristics and may not match your preferred taxonomy.
- Rollback plan JSON files contain local paths. Do not post them publicly without reviewing them.
- If your archive directory is on another disk/filesystem, large GGUF moves may take time.

## Still incomplete or not implemented yet

- Router live-model blocking via `/v1/models`.
- User-configurable grouping/tag rules beyond the initial `--group lab` helper.
- Optional checksum verification for very large cross-device moves.
- Hugging Face download flows.
- Full GGUF-driven settings recommendation and hardware auto-detection.
- Broader Hugging Face/update metadata storage beyond the current repo/file based freshness checks.

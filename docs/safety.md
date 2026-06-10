# Safety model

`llama-modelctl` is designed for local GGUF model inventories where mistakes can be expensive: a wrong move can break a running router, waste large disk copies, or remove a model that another service depends on.

## Safe-by-default commands

These commands are read-only with respect to the router ini and model files:

- `setup` without `--yes`
- `import`
- `doctor`
- `list`
- `show`
- `aliases`
- `delete`
- `archive` without `--yes`
- `rollback` without `--yes`

## Mutating commands

Only these paths intentionally mutate files:

- `setup --yes`: writes modelctl's own config and registry only; it does not edit the router ini.
- `archive ... --yes`: edits the router ini, writes an ini backup, moves model files, and writes rollback metadata.
- `rollback ... --yes`: moves archived files back and restores the router ini from backup metadata.

## Archive safeguards

Archive apply currently requires:

- an explicit `--yes` flag;
- existing source files;
- non-existing destinations;
- a router ini backup;
- rollback plan metadata;
- atomic text writes for ini, backup, and plan files;
- rollback backup hash verification when available.

## Operational cautions

- Stop or reload your router after changing aliases if clients need the live `/v1/models` catalogue to reflect the new ini.
- Review archive destinations before applying. Archive folder naming uses filename heuristics and may not match your preferred taxonomy.
- Rollback plan JSON files contain local paths. Do not post them publicly without reviewing them.
- If your archive directory is on another disk/filesystem, large GGUF moves may take time.

## Not implemented yet

- Mutating delete.
- Router live-model blocking via `/v1/models`.
- User-configurable grouping/tag rules beyond the initial `--group lab` helper.
- Optional checksum verification for very large cross-device moves.

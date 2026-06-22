# modelctl Requirements and Implementation Status

Last updated: 2026-06-22

This root document is the project entry point for product requirements and current implementation status. The detailed product requirements remain in [`docs/requirements.md`](docs/requirements.md); the implementation sequence remains in [`docs/roadmap.md`](docs/roadmap.md); small follow-up work is tracked in [`docs/backlog.md`](docs/backlog.md).

## Product goal

`modelctl` is a deterministic, safe-by-default local model operations CLI for `llama.cpp` router mode. It manages a router `.ini` file, model aliases, GGUF model files, archive/delete/recovery metadata, benchmarks, monitoring metadata, and agent/website-readable output.

The tool should let humans, Hermes agents, OpenCode, and simple local dashboards inspect and operate the local model setup without guessing paths, aliases, service names, endpoints, or model suitability.

## Core requirements

- Manage an existing or newly-created `llama.cpp` router `.ini` file.
- Import aliases, model paths, enabled/disabled state, and runtime settings from the router `.ini`.
- Keep modelctl-owned configuration, data, state, recovery manifests, benchmarks, logs, and temporary files out of the user home root.
- Provide deterministic human output and stable JSON output for automation.
- Treat read-only commands as non-mutating.
- Treat routine reversible actions such as add, enable, disable, archive, restore, and recover as automatable.
- Require explicit confirmation or explicit apply semantics for destructive delete.
- Keep archive/restore/delete/recover surgical: only the relevant model file, aliases, sections, and manifests should change.
- Provide router launch/monitoring guidance without hard-coding private hostnames, service names, or local agent names.
- Build toward evidence-based model choice using benchmark history, reliability records, and recommendation rules.

## Current implemented command surface

The current CLI exposes:

```text
setup, import, doctor, list, show, aliases, delete, archive,
update-check, enable, disable, add, add-entry, benchmark, scan,
restore, recover, monitor, rules
```

`add-entry` is retained only as a deprecated compatibility alias for `add`.

## Implemented / mostly implemented

- Existing router `.ini` import via `setup` and `import`.
- Basic operational health checks via `doctor`.
- Model and alias inspection via `list`, `show`, and `aliases`.
- Plain numeric target IDs and explicit target forms such as `alias:<name>` and `path:<file>`.
- List filters for active/archive and enabled/disabled views.
- Add/enable/disable operations that preserve unrelated `.ini` content.
- Archive operation with aliases preserved by default and optional alias disabling.
- Restore operation for archived model files with conflict-aware behaviour.
- Delete dry-run impact preview and guarded destructive delete with focused recovery manifest generation.
- Recover operation from delete recovery manifests.
- Stable JSON output envelope for supported automation paths.
- Storage hygiene for modelctl-owned config/data/state/cache/recovery/benchmark locations.
- Real `llama-bench` invocation path for `benchmark` when the binary is available, with persisted result display in `show`.
- Hugging Face freshness/update state persistence when source metadata is known.
- Read-only `monitor discover` for configured/common local OpenAI-compatible endpoints.
- File-backed `monitor router` log reading.
- Clear monitor guidance when no monitor backend is configured, including `modelctl monitor discover` as the suggested next command.
- Documentation for safety, JSON output, lifecycle operations, settings rules, release readiness, roadmap, and backlog.

## Features still to build

### Setup and onboarding

- Create a new router `.ini` from scratch when no existing ini is available.
- Add a wizard-first setup flow that asks for active model directories, archive storage, binary path, endpoint, monitoring backend, and intended usage.
- Generate explicit `llama-server` router launch guidance from configured metadata.
- Store and display configured router binary/service/container/process details.

### Router management

- Add first-class `router status` / `router command` support.
- Add configured `router reload` and `router restart` actions where safe and explicitly requested.
- Keep router actions backend-driven rather than guessing service names or process IDs.

### Monitoring

- Implement additional monitor backends beyond current file/discovery support: systemd, container/docker, process/modelctl-managed logs, and safe configured command backend.
- Decide whether read-only process-list discovery is worth adding; if added, it must avoid guessing persistent configuration.
- Add support for richer monitor options such as `--follow` and `--since` where the backend supports them.

### Benchmarking and recommendations

- Expand benchmark comparison across runtime settings and models.
- Track memory usage and context/runtime settings in richer benchmark records.
- Feed benchmark history into recommendations.
- Implement `classify` for model/use-case suitability.
- Implement `recommend` for coding, chat, agent, archive, and alias-setting decisions.
- Add evidence-based active model hygiene recommendations.

### Source metadata and downloads

- Expand source metadata tracking: provider/repo, filename, size, hash, quantisation, download date, and trust level.
- Add Hugging Face search / plan-download / download workflows.
- Download through modelctl-owned temporary files, verify metadata where available, and atomically place GGUFs in configured storage.
- Optionally chain successful downloads into `modelctl add`.

### Learning and reliability records

- Persist reliability observations, context stability findings, JSON/tool-call stability, keep/archive/delete rationale, user overrides, failed experiments, and successful mitigations.
- Use those records in classification and recommendation output.

### Website and agent readiness

- Stabilise JSON schemas for all command areas, not just the currently covered paths.
- Add website-friendly status/action outputs and integration tests.
- Add machine-readable recommendation rationale and router/server state.
- Add clear error codes consistently across commands.

### Documentation and release polish

- Add dedicated router ini and monitoring documentation files if the feature set keeps growing.
- Keep `docs/backlog.md` synchronized with completed slices and newly discovered small amendments.
- Finish release checklist items before treating the project as public/stable.

## Current backlog snapshot

See [`docs/backlog.md`](docs/backlog.md). As of this update:

- Completed: missing-target help UX, list filters, monitor unconfigured guidance.
- Partially complete: monitor discovery; only optional process-list discovery remains undecided.
- Next high-value slices: setup/router launch guidance, router status/command, richer monitor backends, and recommendation/classification pipeline.

## Verification baseline

Current verification command:

```bash
python3 -m py_compile modelctl.py modelctl_core.py
python3 -m unittest discover -s tests -v
```

Latest verified result on 2026-06-22: 108 tests passed, 1 skipped.

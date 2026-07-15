# modelctl Roadmap

This document tracks implementation direction and priorities for modelctl.

The product reference is `docs/requirements.md`. That document describes the intended feature set. This roadmap explains how to get there in a practical order.

modelctl is specifically focused on managing `llama.cpp` router mode: a router `.ini` file, the aliases inside it, the GGUF model files referenced by those aliases, and the local operations needed by humans, Hermes agents, OpenCode, and simple websites.

---

## 1. Guiding Direction

The core product direction is:

* Manage a `llama.cpp` router `.ini` file.
* Help users create or import that `.ini` file.
* Help users call `llama.cpp` correctly with that `.ini` file.
* Manage model aliases without manual `.ini` editing.
* Manage active and archived GGUF model files.
* Benchmark model files and runtime settings independently from aliases.
* Recommend good alias configurations for the current hardware and usage.
* Provide deterministic JSON output for agents and websites.
* Avoid polluting the user’s home root folder.
* Require explicit confirmation only for destructive model deletion.

The roadmap should avoid designs that make the tool approval-heavy. Routine reversible actions should be automatable.

---

## 2. Current Product Cleanup Priorities

### 2.1 Remove obsolete lifecycle language

The old lifecycle model treated archive and rollback as a pair. That direction is obsolete.

Replace it with:

* `archive` - move a model from active storage to archive storage.
* `restore` - move an archived model back to active storage.
* `delete` - delete a model file and remove or disable relevant alias/router configuration.
* `recover` - use delete recovery metadata to reconstruct relevant alias/section configuration after the model is restored or redownloaded.

Required cleanup:

* Remove standard lifecycle use of `rollback`.
* Remove references to full-router configuration restore as a normal lifecycle operation.
* Rename or replace `docs/archive-and-rollback.md`.
* Remove obsolete tests that validate archive rollback as the normal recovery model.
* Ensure delete/recover metadata is surgical and stores only affected alias/section configuration.

### 2.2 Rename add-entry to add

The user-facing command should be:

```bash
modelctl add
```

Not:

```bash
modelctl add-entry
```

Migration should include:

* CLI command rename.
* Backward-compatible alias if useful.
* Documentation update.
* Tests for `add`.
* Deprecation note for `add-entry` if retained temporarily.

### 2.3 Remove public references to private agent names

Documentation and public files should refer to:

* Hermes agents
* OpenCode
* local agents
* websites or dashboards

They should not reference private local agent names.

Any document or code comment referring to private agent names should be rewritten generically.

---

## 3. Storage and Directory Hygiene

modelctl must not create random files in the user’s home root folder.

Implementation should standardise storage locations.

Recommended Linux defaults:

```text
~/.config/modelctl/        configuration
~/.local/share/modelctl/   persistent modelctl data
~/.local/state/modelctl/   logs, state, run history
~/.cache/modelctl/         cache and temporary files
```

Required work:

* Define modelctl-owned config/data/state/cache paths.
* Store recovery manifests under a modelctl recovery directory.
* Store benchmark history under a modelctl benchmark directory.
* Store learning logs under a modelctl learning directory.
* Store modelctl-managed router logs under modelctl state/log storage.
* Ensure `doctor` checks these directories.
* Ensure setup creates them if needed.
* Ensure tests do not require files in the user’s home root folder.

Acceptance criteria:

* No modelctl command should create ad hoc files directly under `~/`.
* All persistent modelctl artefacts should be discoverable through `modelctl status` or `modelctl doctor`.
* Configured paths should be overrideable.

---

## 4. Setup and Router ini Onboarding

Setup is foundational because modelctl is useful only if it knows the router `.ini`, model directories, and how the router is run.

### 4.1 Existing ini import

Setup should support users who already have a `llama.cpp` router `.ini`.

Required behaviour:

* Ask for or discover router `.ini` path.
* Validate that the file exists.
* Parse aliases and runtime settings.
* Detect referenced GGUF files.
* Detect missing model paths.
* Store the router `.ini` path in modelctl config.
* Import aliases into the registry.

Command shape:

```bash
modelctl setup
modelctl setup --ini /path/to/llama-models.ini
modelctl import
```

### 4.2 New ini creation

If no router `.ini` exists, setup should offer to create one.

Required behaviour:

* Ask where to store the `.ini`.
* Ask where active model files are stored.
* Scan for GGUF files.
* Propose initial aliases.
* Propose conservative runtime settings.
* Write a minimal valid router `.ini`.
* Store the new `.ini` path in modelctl config.
* Show the command needed to start `llama.cpp` router mode with the `.ini`.

Command shape:

```bash
modelctl setup --create-ini
```

### 4.3 llama.cpp launch guidance

modelctl should help the user understand how to launch the router with the configured `.ini`.

Required behaviour:

* Store `llama-server` or router binary path where configured.
* Store router launch command or service details.
* Provide a command to display launch guidance.

Command shape:

```bash
modelctl router command
modelctl doctor
```

Output should explain:

* The `.ini` file in use.
* The configured binary or service.
* The equivalent manual command where known.
* The configured endpoint where known.

---

## 5. Baseline Router ini Management

The first stable product baseline should make `.ini` maintenance easy.

### 5.1 Inspect aliases

Commands:

```bash
modelctl aliases
modelctl show alias:<name>
modelctl list
```

Required behaviour:

* Show aliases.
* Show model paths.
* Show enabled/disabled state.
* Show runtime settings.
* Show missing target files.
* Show duplicate alias targets.
* Support JSON output.

### 5.2 Add alias/model entry

Command:

```bash
modelctl add
```

Required behaviour:

* Add a GGUF model file to the router `.ini`.
* Create one or more aliases.
* Suggest alias names.
* Suggest runtime settings.
* Preserve unrelated `.ini` content.
* Report what changed.
* Support JSON output.

This is a routine mutating command and should not require explicit confirmation by default when the target is clear.

### 5.3 Enable and disable aliases

Commands:

```bash
modelctl enable alias:<name>
modelctl disable alias:<name>
```

Required behaviour:

* Enable or disable the selected alias.
* Preserve unrelated `.ini` content.
* Report what changed.
* Support JSON output.

These are routine mutating commands and should not require explicit confirmation by default.

---

## 6. Lifecycle: Archive, Restore, Delete, Recover

### 6.1 Archive

Command:

```bash
modelctl archive <model-or-alias>
```

Required behaviour:

* Move the model file from active storage to archive storage.
* Preserve aliases by default.
* Record movement metadata sufficient for restore.
* Report what changed.
* Support JSON output.

Optional behaviour:

```bash
modelctl archive <model-or-alias> --disable-aliases
```

If used, this should disable only aliases directly linked to the archived model.

Archive is routine reversible storage management and should not require explicit confirmation by default.

### 6.2 Restore

Command:

```bash
modelctl restore <model-or-alias-or-archive-id>
```

Required behaviour:

* Move the archived model back to active storage.
* Preserve unrelated `.ini` changes.
* Re-enable aliases only if archive metadata confirms they were disabled by archive.
* Detect conflicts.
* Fail clearly if the target path already exists or metadata is incomplete.
* Support JSON output.

Restore is routine reversible storage management and should not require explicit confirmation by default unless a conflict requires an explicit override.

### 6.3 Delete

Command:

```bash
modelctl delete <model-or-alias> --apply
```

Required behaviour:

* Delete the model file.
* Remove or disable only relevant aliases/sections.
* Create a JSON recovery manifest before applying.
* Save only relevant alias/section configuration, not the whole router `.ini`.
* Include source metadata where known.
* Include model filename, size, hash, and redownload source where available.
* Show what will be deleted before applying.
* Require explicit confirmation or an explicit apply flag.
* Support JSON output.

Delete is the normal destructive lifecycle command.

### 6.4 Recover

Command:

```bash
modelctl recover <recovery-manifest.json>
```

Required behaviour:

* Read delete recovery metadata.
* Verify whether the model file exists again or has been redownloaded.
* Restore only relevant aliases/sections.
* Preserve unrelated `.ini` changes.
* Detect conflicts.
* Fail clearly if recovery cannot be completed.
* Support JSON output.

Recover should not require explicit confirmation by default unless it would overwrite current configuration.

---

## 7. Router Management and Monitoring

### 7.1 Router status

Command:

```bash
modelctl router status
```

Required behaviour:

* Show configured router `.ini`.
* Show configured endpoint.
* Show configured service/container/process metadata where available.
* Check whether the router appears to be running.
* Show actionable errors if status cannot be determined.

### 7.2 Router reload and restart

Commands:

```bash
modelctl router reload
modelctl router restart
```

Required behaviour:

* Use configured service/process/container metadata.
* Report the backend being used.
* Fail clearly if no backend is configured.
* Report success/failure.
* Support JSON output.

These are operational actions. They should not require confirmation every time when explicitly requested.

### 7.3 Monitor

Command:

```bash
modelctl monitor
modelctl monitor router
modelctl monitor router --lines 200
modelctl tail 8080
modelctl router logs cuda
```

`modelctl monitor router --follow` remains a compatibility path for configured monitor backends, but primary human log-follow UX should prefer `tail` or `router logs`.

Required behaviour:

* Show recent router/server logs.
* Follow logs where supported.
* Hide platform-specific commands behind modelctl.
* Show the monitoring backend being used.
* Show the internal command where useful.
* Support JSON-friendly metadata output.

Supported backends:

* `systemd` using `journalctl -u <service>`.
* `file` using a configured log file.
* `docker` or `container` using container logs.
* `process` for modelctl-managed process logs.
* `command` for a configured safe read-only log command.
* `none` where monitoring is not configured.

Setup should ask how the router is run and configure monitoring accordingly.

Monitor is read-only. It must not restart, reload, kill, or modify anything.

---

## 8. Benchmarking and Runtime Setting Optimisation

Benchmarking is alias-independent.

The purpose of benchmarking is to evaluate a model file and runtime settings so modelctl can recommend the best alias configuration for the current hardware and usage.

Command shapes:

```bash
modelctl benchmark /path/to/model.gguf
modelctl benchmark /path/to/model.gguf --ctx-size 8192 --ngl 99
modelctl benchmark --compare /path/to/model.gguf
modelctl benchmark --for-use coding
```

Required behaviour:

* Run benchmark against a model file and runtime settings.
* Store benchmark results in a modelctl-owned benchmark directory.
* Track prompt throughput.
* Track generation throughput.
* Track memory usage where possible.
* Track context size and runtime settings used.
* Compare settings for the same model.
* Compare models for the same use case.
* Feed results into recommendations.

Benchmark should help answer:

* What settings perform best on this hardware?
* Which context size is practical?
* Which GPU-layer setting works best?
* Which alias settings should be created for coding, chat, reasoning, or testing?
* Is the performance gain worth the memory cost?

Benchmarking should not depend on an alias existing first. Instead, benchmark results should inform alias configuration.

---

## 9. Classification and Recommendations

### 9.1 Classify

Command:

```bash
modelctl classify <model-or-file>
```

Required behaviour:

* Classify suitability by use case.
* Use filename metadata, GGUF metadata, benchmark results, and reliability records where available.
* Mark uncertain conclusions as inferred.

Use cases:

* Coding/tool use.
* Reasoning/planning.
* Fast chat.
* Long-context testing.
* Summarisation.
* Agent workflows.
* Experimental use.
* Archive candidacy.

### 9.2 Recommend

Command:

```bash
modelctl recommend --for coding
modelctl recommend --for chat
modelctl recommend --for agent
modelctl recommend --for archive
modelctl recommend --for alias-settings /path/to/model.gguf
```

Required behaviour:

* Recommend models, aliases, or runtime settings.
* Use benchmark history.
* Use reliability history.
* Use hardware capability.
* Use current `.ini` state.
* Explain rationale.
* Support JSON output.

Recommendations should favour a small curated active model set.

---

## 10. Source Metadata, Freshness, and Download

### 10.1 Source metadata

modelctl should track where model files came from.

Metadata should include:

* Source repository or provider.
* Model filename.
* Expected size.
* Expected hash where available.
* Quantisation.
* Download date where known.
* Local file status.
* Trust level.

### 10.2 Update check

Command:

```bash
modelctl update-check
modelctl update-check <model-or-file>
```

Required behaviour:

* Compare local model files with known source metadata.
* Report whether the local file appears current.
* Report missing source metadata.
* Report missing local files.
* Report hash or size mismatches where known.
* Never replace a local model without clear user intent.

### 10.3 Download

Command shapes:

```bash
modelctl hf search qwen --max-params 14B
modelctl hf plan-download unsloth/Qwen3.6-35B-A3B-GGUF --quant UD-Q5_K_XL
modelctl hf download unsloth/Qwen3.6-35B-A3B-GGUF --quant UD-Q5_K_XL
```

Required behaviour:

* Query Hugging Face model metadata and GGUF file trees.
* Prefer repos with `llama.cpp`/GGUF support.
* Download to a modelctl-owned temporary file first.
* Verify size/checksum metadata when available.
* Atomically place the GGUF into the configured model directory.
* Optionally add an alias using `modelctl add`.
* Avoid polluting the user’s home root folder.

---

## 11. Learning Log and Reliability Records

modelctl should learn from usage.

Required records:

* Benchmark history.
* Recommendation history.
* Reliability observations.
* Context stability findings.
* Tool-call stability findings.
* JSON reliability findings.
* Keep/archive/delete decisions.
* User overrides.
* Failed experiments.
* Successful mitigations.

These records should support better future recommendations.

Storage must use modelctl-owned data/state directories.

---

## 12. Agent and Website Integration

modelctl should be callable by:

* Hermes agents.
* OpenCode.
* Simple websites.
* Dashboards.
* Other local tools.

Required integration behaviours:

* Stable JSON output.
* Deterministic command behaviour.
* Clear error states.
* Machine-readable lifecycle state.
* Machine-readable router/server state.
* Machine-readable monitoring metadata.
* Machine-readable recommendation rationale.

Useful website actions:

* Show status.
* List models.
* Show model details.
* Add alias.
* Enable alias.
* Disable alias.
* Archive model.
* Restore model.
* Benchmark model/settings.
* Recommend alias settings.
* Monitor router logs.
* Delete model with confirmation.
* Recover configuration from manifest.

---

## 13. Documentation Cleanup

Documentation should be reorganised around the new product model.

Required cleanup:

* Keep `docs/requirements.md` as the product reference.
* Keep `docs/roadmap.md` as implementation direction and sequencing.
* Replace `docs/archive-and-rollback.md` with archive/restore/delete/recover documentation.
* Update `docs/safety.md` so it reflects minimal-friction automation.
* Remove approval-heavy wording except for delete.
* Remove private local agent names.
* Remove normal lifecycle references to rollback.
* Document `llama.cpp` router `.ini` usage clearly.
* Document setup, monitor, and storage paths.

Suggested documentation files:

```text
docs/requirements.md
docs/roadmap.md
docs/archive-restore-delete-recover.md
docs/router-ini.md
docs/monitoring.md
docs/safety.md
docs/settings-rules.md
```

---

## 14. Implementation Sequence

### Phase 1 - Documentation and terminology correction

* Rewrite requirements.
* Rewrite roadmap.
* Replace archive/rollback documentation.
* Update safety documentation.
* Remove private agent names.
* Remove normal lifecycle references to rollback.
* Rename `add-entry` direction to `add`.

### Phase 2 - Baseline command cleanup

* Implement or alias `add`.
* Ensure `setup`, `import`, `scan`, `list`, `show`, `aliases`, `doctor`, and `rules` match the documented baseline.
* Ensure JSON output is consistent for agent and website use.
* Ensure all modelctl files are stored in modelctl-owned directories.

### Phase 3 - Archive and restore

* Change archive so aliases are preserved by default.
* Add optional `--disable-aliases`.
* Add restore.
* Store archive movement metadata.
* Preserve unrelated `.ini` changes.
* Add conflict detection.
* Add tests.

### Phase 4 - Delete and recover

* Ensure delete requires confirmation or explicit apply.
* Ensure delete writes a recovery manifest.
* Save only affected alias/section configuration.
* Add recover.
* Preserve unrelated `.ini` changes.
* Add tests.

### Phase 5 - Router setup and monitoring

* Improve setup for existing or new router `.ini`.
* Show `llama.cpp` launch command guidance.
* Configure monitoring backend.
* Add `monitor`.
* Support systemd, file, container, process, and command backends where practical.
* Add tests for configured backend behaviour.

### Phase 6 - Benchmark and recommendations

* Make benchmark model-file and runtime-setting based.
* Store benchmark history.
* Compare settings.
* Recommend alias runtime settings.
* Add classify.
* Add recommend.
* Add evidence-based active model hygiene.

### Phase 7 - Website and agent readiness

* Stabilise JSON schemas.
* Add website-friendly command outputs.
* Add monitoring metadata.
* Add recommendation metadata.
* Add clear error codes.
* Add integration tests for local agent and website workflows.

---

## 15. Non-Goals and Avoided Direction

Avoid:

* Treating archive as destructive.
* Disabling aliases by default during archive.
* Using rollback as the standard lifecycle command.
* Restoring whole router `.ini` files as normal recovery.
* Polluting the user’s home root folder.
* Requiring confirmation for routine reversible operations.
* Hard-coding one user’s service names, paths, or local agent names.
* Making modelctl a full process supervisor.
* Making the requirements document a status tracker.

The product should remain practical: automate routine work, confirm destructive deletion, and give clear deterministic output for humans, agents, and websites.

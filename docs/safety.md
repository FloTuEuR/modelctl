# Safety Model

modelctl is designed for local `llama.cpp` router-mode environments.

The tool manages:

* a router `.ini` file
* model aliases
* alias runtime settings
* GGUF model files
* active model storage
* archive model storage
* delete recovery metadata
* benchmark and reliability records
* router monitoring configuration

The safety model is intentionally practical. modelctl exists to make model management easier, not to interrupt the user with approval prompts for every routine action.

The core rule is:

* Read-only commands must not mutate state.
* Routine reversible commands may apply directly.
* Deleting a model is destructive and requires explicit confirmation or an explicit apply flag.

---

## 1. Safety Philosophy

modelctl should reduce manual risk by making operations deterministic and scoped.

The user should not need to manually edit router `.ini` files, remember log commands, move GGUF files by hand, or reconstruct aliases from memory.

Safety comes from:

* clear command behaviour
* scoped changes
* deterministic output
* modelctl-owned storage locations
* relevant recovery metadata
* conflict detection
* actionable errors

Safety should not mean unnecessary approval prompts.

Routine operations should be easy to automate for humans, Hermes agents, OpenCode, and simple websites.

---

## 2. Command Risk Levels

modelctl commands fall into three broad categories.

### Read-only commands

Read-only commands do not modify router `.ini` files, model files, services, logs, registry state, or modelctl persistent state except for harmless cache reads where applicable.

Examples:

* `status`
* `list`
* `show`
* `aliases`
* `doctor`
* `rules`
* `update-check` when only reporting
* `classify` when only reporting
* `recommend` when only reporting
* `monitor`
* `router status`
* `router command`

Read-only commands must be safe for agents and websites to run frequently.

### Routine mutating commands

Routine mutating commands make scoped, expected, reversible, or non-destructive changes.

They do not require explicit confirmation by default.

Examples:

* `setup`
* `import`
* `scan`
* `add`
* `enable`
* `disable`
* `archive`
* `restore`
* `recover`
* `benchmark`
* `router reload`
* `router restart`
* metadata updates
* learning-log updates

These commands must:

* report what changed
* affect only relevant files, aliases, sections, or metadata
* preserve unrelated router `.ini` content
* store modelctl artefacts in modelctl-owned locations
* fail clearly on conflicts
* provide JSON output where agents or websites may use them

### Destructive commands

Destructive commands remove model files or erase useful configuration.

The normal destructive command is:

* `delete`

`delete` must require explicit confirmation or an explicit apply flag.

Before applying, delete must show:

* model file to be deleted
* aliases or sections to be removed or disabled
* recovery manifest path
* source metadata available for future recovery
* whether recovery is likely to be possible later

---

## 3. Confirmation Policy

Only destructive model deletion requires confirmation by default.

Routine commands must not require confirmation merely because they modify configuration.

Commands that should not normally require confirmation:

* `add`
* `enable`
* `disable`
* `archive`
* `restore`
* `recover`
* `import`
* `scan`
* `benchmark`
* `router reload`
* `router restart`

A routine command should fail clearly rather than ask repeated questions when it encounters a conflict.

Examples of conflicts:

* restore target file already exists
* alias already points to a different model
* recovery manifest is incomplete
* router `.ini` cannot be parsed
* configured directory is unavailable
* monitoring backend is missing
* configured service/container/log file cannot be found

The user or agent can then rerun a more explicit command or override option where appropriate.

---

## 4. Router ini Safety

The router `.ini` file is central to modelctl.

modelctl must preserve unrelated `.ini` content when changing aliases or sections.

Commands that edit the `.ini` must:

* modify only the relevant alias or section
* preserve unrelated aliases
* preserve unrelated comments where practical
* preserve unrelated runtime settings
* avoid whole-file replacement unless specifically required by the operation
* write atomically where practical
* report the affected aliases and sections

modelctl must not use full-router configuration restoration as the normal way to undo lifecycle actions.

Archive/restore and delete/recover must be surgical.

---

## 5. Setup Safety

`setup` is a routine mutating command.

It may write modelctl-owned configuration and state files.

It may create a new router `.ini` file when the user chooses to create one.

Setup must:

* avoid overwriting an existing `.ini` without explicit user intent
* store modelctl configuration in modelctl-owned paths
* configure active and archive model directories
* configure router launch metadata where available
* configure monitoring metadata where available
* explain how to launch `llama.cpp` router mode with the configured `.ini`
* avoid creating random files in the user’s home root folder

Re-running setup must not destroy existing configuration unless the user explicitly chooses replacement behaviour.

---

## 6. Storage Safety

modelctl must not pollute the user’s home root folder.

Configuration, state, logs, temporary files, recovery manifests, benchmark results, and learning records must live in modelctl-owned locations.

Recommended Linux layout:

```text
~/.config/modelctl/        configuration
~/.local/share/modelctl/   persistent data
~/.local/state/modelctl/   logs, state, run history
~/.cache/modelctl/         cache and temporary files
```

The exact locations should be configurable.

modelctl-owned artefacts include:

* registry files
* recovery manifests
* archive metadata
* benchmark results
* learning logs
* monitoring configuration
* modelctl-managed router logs
* temporary download files
* temporary benchmark files

No command should create ad hoc files directly under `~/`.

---

## 7. Archive Safety

`archive` is reversible storage management.

It should move a model file from active storage to archive storage.

Archive does not require explicit confirmation by default.

Archive must:

* preserve aliases by default
* move only the selected model file
* write archive movement metadata sufficient for restore
* report source and destination paths
* preserve unrelated router `.ini` content
* avoid disabling aliases unless explicitly requested

Optional behaviour:

```bash
modelctl archive <model-or-alias> --disable-aliases
```

When `--disable-aliases` is used, modelctl must disable only aliases directly linked to the archived model.

Archive must not:

* delete the model file permanently
* remove unrelated aliases
* disable aliases by default
* rewrite unrelated router `.ini` sections

---

## 8. Restore Safety

`restore` is the opposite of archive.

It moves an archived model file back to active storage.

Restore does not require explicit confirmation by default.

Restore must:

* move only the relevant archived model file
* restore it to the correct active location
* preserve unrelated router `.ini` content
* re-enable aliases only if archive metadata confirms they were disabled by archive
* detect conflicts before applying
* fail clearly if the target file already exists or archive metadata is incomplete

Restore must not:

* replace the whole router `.ini`
* erase unrelated changes made after archive
* recreate unrelated aliases
* overwrite an existing active model file without an explicit conflict-resolution option

---

## 9. Delete Safety

`delete` is destructive lifecycle management.

It removes a model file and removes or disables relevant alias/router configuration.

Delete requires explicit confirmation or an explicit apply flag.

Before applying, delete must:

* show the model file to be deleted
* show relevant aliases and sections affected
* show whether aliases will be removed or disabled
* create or show the recovery manifest path
* show source metadata available for future recovery
* explain whether recovery is likely to be possible later

Delete must create a JSON recovery manifest before destructive changes are applied.

The recovery manifest must contain only relevant recovery data, such as:

* deleted model path
* model filename
* model size and hash where available
* source repository or redownload metadata where known
* affected aliases only
* affected sections only
* removed alias configuration only
* delete timestamp
* user note or reason where provided

Delete must not:

* remove unrelated aliases
* rewrite unrelated router `.ini` sections
* store a full router `.ini` as the normal recovery model
* destroy useful recovery metadata
* proceed without explicit confirmation or apply mode

---

## 10. Recover Safety

`recover` uses a delete recovery manifest.

Recover reconstructs relevant alias or section configuration after a deleted model has been restored or redownloaded.

Recover does not require explicit confirmation by default.

Recover must:

* read the recovery manifest
* verify whether the model file exists again
* restore only the relevant aliases or sections
* preserve unrelated router `.ini` changes
* detect conflicts before applying
* fail clearly if recovery cannot be completed
* report what was restored and what could not be restored

Recover must not:

* restore the whole old router `.ini`
* overwrite unrelated aliases
* assume the model file exists unless verified
* hide conflicts from users, agents, or websites

---

## 11. Add, Enable, Disable, and Scan Safety

### add

`add` is a routine mutating command.

It may add a model entry or alias to the router `.ini`.

It should:

* add only the requested model or alias
* preserve unrelated `.ini` content
* report what changed
* use modelctl-owned metadata storage
* avoid confirmation by default when the target is clear

### enable

`enable` is a routine mutating command.

It should:

* enable only the selected alias
* preserve unrelated `.ini` content
* report what changed
* avoid confirmation by default

### disable

`disable` is a routine mutating command.

It should:

* disable only the selected alias
* preserve unrelated `.ini` content
* report what changed
* avoid confirmation by default

### scan

`scan` should inspect configured model directories.

If scan creates registry updates or suggested entries, it must store them in modelctl-owned locations.

If scan writes to the router `.ini`, it must preserve unrelated content and report exactly what was added.

---

## 12. Benchmark Safety

`benchmark` evaluates model files and runtime settings.

Benchmarking is alias-independent.

Benchmark should help find the best alias configuration for the current hardware and intended use.

Benchmark does not require explicit confirmation by default.

Benchmark must:

* store benchmark results in modelctl-owned storage
* report the model file and runtime settings tested
* avoid modifying router aliases unless explicitly requested through a separate command
* avoid polluting the user’s home root folder
* fail clearly if the benchmark binary or model file cannot be found

Benchmark may use temporary files, but they must live in a modelctl-owned cache/temp directory or a safe runtime temp area.

---

## 13. Router Operation Safety

Router commands should use configured router metadata rather than guessed service names or paths.

### router status

`router status` is read-only.

It should not mutate service state.

### router command

`router command` is read-only.

It should show how to launch `llama.cpp` router mode with the configured `.ini`.

### router reload

`router reload` is an explicit operational command.

It may reload the configured router/server where supported.

It should not require confirmation by default because the user explicitly requested the operational action.

It must fail clearly if no backend is configured.

### router restart

`router restart` is an explicit operational command.

It may restart the configured router/server where supported.

It should not require confirmation by default because the user explicitly requested the operational action.

It must fail clearly if no backend is configured.

Router reload/restart commands must:

* report the backend being used
* report success or failure
* avoid guessing service/container names
* use configured modelctl router metadata
* provide JSON output where needed

---

## 14. Monitor Safety

`monitor` is read-only.

It exists so the user does not need to remember platform-specific log commands.

Examples:

* `journalctl -u <service> -f`
* `tail -f <log-file>`
* `docker logs -f <container>`

monitor may support backends such as:

* systemd
* file
* docker/container
* modelctl-managed process
* configured read-only command
* none

monitor must not:

* restart services
* reload the router
* kill processes
* edit router configuration
* edit model files
* edit aliases
* create files outside modelctl-owned paths

monitor should:

* show recent logs
* follow logs where supported
* show the backend being used
* show the service/container/log identifier where appropriate
* fail clearly when no monitoring backend is configured
* expose machine-readable metadata for agents and websites

---

## 15. Download and Update Safety

Download and update workflows must avoid corrupting active model storage.

Download should:

* use a modelctl-owned temporary location first
* verify size or checksum metadata where available
* move the completed file atomically into model storage where practical
* avoid overwriting an existing model file without explicit user intent
* store source metadata in modelctl-owned data storage
* avoid polluting the user’s home root folder

Update-check is read-only unless explicitly asked to update metadata.

Replacing a model file must be treated as an explicit user-intended operation.

---

## 16. Agent and Website Safety

Hermes agents, OpenCode, simple websites, and dashboards should call modelctl instead of guessing local state.

Clients should not guess:

* router `.ini` location
* model file paths
* service names
* container names
* endpoints
* aliases
* runtime settings
* monitoring backend
* whether a model is suitable for a task

modelctl should provide deterministic human-readable and JSON-readable outputs.

For clients:

* routine actions should be automatable
* delete must require explicit confirmation/apply workflow
* conflicts should fail clearly
* errors should be actionable
* monitoring must be read-only

---

## 17. Public Documentation Safety

Public documentation must not include private local agent names, private paths, secrets, tokens, or machine-specific details.

Documentation should refer generically to:

* Hermes agents
* OpenCode
* local agents
* websites
* dashboards
* `llama.cpp` router mode
* router `.ini` files

Documentation must not publish:

* private service names if sensitive
* private machine names if not intended
* personal paths
* tokens
* credentials
* private recovery manifests
* private logs

Recovery manifests and logs may contain local paths and operational details. They should be reviewed before sharing publicly.

---

## 18. Operational Cautions

Changing aliases may require router reload or restart before live clients see the updated model catalogue.

Large GGUF file moves may take time, especially across disks or filesystems.

Archive and restore paths should be configured clearly.

Container, systemd, file-log, and manual-process setups may require different monitoring backends.

If monitoring is not configured, `monitor` should explain how to configure it rather than guessing.

If router management is not configured, `router reload` and `router restart` should fail clearly rather than guessing.

---

## 19. Safety Acceptance Criteria

A feature satisfies the safety model when:

* it stores modelctl artefacts in modelctl-owned locations
* it preserves unrelated router `.ini` content
* it reports affected files, aliases, and sections
* it supports deterministic output
* it provides JSON output where agents or websites may use it
* it fails clearly on conflicts
* it avoids unnecessary confirmation for routine actions
* it requires confirmation or explicit apply mode for model deletion
* it avoids guessing local paths, service names, containers, or endpoints
* it avoids publishing private local details in documentation

A lifecycle feature satisfies the safety model when:

* archive preserves aliases by default
* restore is the normal opposite of archive
* delete creates a focused recovery manifest
* recover restores only relevant alias/section configuration
* unrelated router changes are preserved

A monitoring feature satisfies the safety model when:

* monitor is read-only
* the backend is configured, not guessed
* logs can be shown or followed where supported
* errors are clear when monitoring is unavailable

A router operation feature satisfies the safety model when:

* router status is read-only
* reload/restart use configured metadata
* reload/restart do not require confirmation when explicitly requested
* failures are clearly reported

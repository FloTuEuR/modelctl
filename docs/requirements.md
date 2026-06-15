# modelctl Requirements

## 1. Product Vision

modelctl is a deterministic local model operations tool for `llama.cpp` router mode.

It helps users manage a `llama.cpp` router `.ini` file, the GGUF model files referenced by that `.ini` file, and the aliases used by local AI agents, coding tools, and simple local interfaces.

The target user runs one or more local models through `llama.cpp` router mode. The router reads an `.ini` configuration file containing model aliases and runtime settings. modelctl provides a practical, automation-friendly way to inspect, create, maintain, optimise, benchmark, monitor, and clean that `.ini` file without manually editing it.

modelctl should become the deterministic source of truth for:

* Which router `.ini` file is being managed.
* Which model files exist.
* Which aliases exist.
* Which aliases point to which model files.
* Which runtime settings are attached to each alias.
* Which aliases are enabled or disabled.
* Which model files are active.
* Which model files are archived.
* Which model files are missing or broken.
* Which aliases are broken or stale.
* Which alias configuration performs best on the current hardware.
* Which aliases are suitable for specific uses such as coding, reasoning, fast chat, long-context testing, or agent workflows.
* Which models can be archived.
* Which models can be deleted.
* Which deleted configuration can be recovered from a recovery manifest.
* How the router/server is launched, monitored, and diagnosed.

The long-term architecture is:

* `llama.cpp` router serves models using an `.ini` file.
* modelctl manages the model files, aliases, runtime settings, and `.ini` entries behind that router.
* Hermes agents, OpenCode, websites, dashboards, and other clients call modelctl instead of guessing local model state.
* A simple website or local dashboard can use modelctl outputs to expose actions such as list, show, add, enable, disable, archive, restore, delete, recover, benchmark, recommend, monitor, and router health.

Any capable human or AI agent should be able to read this document and understand the intended feature set of modelctl.

This document is a product requirements reference. It is not a roadmap and not a project status tracker.

---

## 2. Product Mission

modelctl must make local model operations easier, more reliable, and more automatable.

The user should not need to:

* Manually inspect large router `.ini` files.
* Remember where each model file is stored.
* Remember which aliases are active.
* Manually compare alias runtime settings.
* Manually move models between active and archive storage.
* Manually work out which alias is best for coding, reasoning, chat, or testing.
* Manually reconstruct alias configuration after a model is deleted and later redownloaded.
* Remember platform-specific router monitoring commands such as `journalctl -u <service> -f`.
* Ask agents to guess service names, endpoints, paths, model suitability, or configuration state.

modelctl must help answer questions such as:

* What router `.ini` file is configured?
* How do I start `llama.cpp` using this `.ini` file?
* What models are available?
* Which models are referenced by the router `.ini` file?
* Which aliases point to which GGUF files?
* Which aliases are enabled or disabled?
* Which aliases have broken or missing model paths?
* Which model files are not yet in the router `.ini`?
* Which aliases are suitable for coding agents?
* Which aliases are suitable for reasoning or planning?
* Which aliases are reliable for tool calls and JSON output?
* Which model or alias should Hermes, OpenCode, or a website choose for a task?
* Which model files should be archived to save active storage space?
* Which model files should be deleted?
* Which aliases should be cleaned up?
* Which alias runtime settings perform best on this hardware?
* Is the router running?
* Where are the router logs?
* How can I follow the router logs?
* Is the modelctl/router setup healthy?

modelctl should reduce operational uncertainty, support automation, and make local AI model management practical for daily use.

---

## 3. Scope

modelctl is focused on local model operations for `llama.cpp` router mode.

It should manage:

* Router `.ini` files.
* Model aliases.
* Alias runtime settings.
* GGUF model files.
* Active model storage.
* Archive model storage.
* Delete recovery metadata.
* Benchmark results.
* Reliability observations.
* Source metadata.
* Router/server launch metadata.
* Router/server monitoring metadata.
* Agent-readable status and recommendation output.
* Website-readable status and action output.
* Setup guidance for running `llama.cpp` router mode with the configured `.ini` file.

modelctl is not intended to be:

* A full `llama.cpp` replacement.
* A training system.
* A cloud model manager.
* A generic file manager.
* A web server by default.
* A general-purpose service supervisor.

modelctl may power a simple website or dashboard, but the core product remains a deterministic CLI and local state manager.

---

## 4. Storage and File Location Requirements

modelctl must not pollute the user’s home root folder.

Configuration, state, logs, temporary files, recovery files, benchmark results, and learning records must be stored in modelctl-owned locations.

Preferred storage principles:

* Configuration should live under a modelctl configuration directory.
* Persistent state should live under a modelctl data directory.
* Logs and run history should live under a modelctl state or log directory.
* Temporary files should live under a modelctl temporary/cache directory or safe runtime temp area.
* Recovery manifests should live under a modelctl recovery directory.
* Benchmark history should live under a modelctl benchmark directory.
* Learning records should live under a modelctl learning directory.
* Router/server monitoring configuration should live under modelctl configuration.
* modelctl-managed router/server logs should live under modelctl state/log storage.

Recommended default layout should follow platform best practice where possible.

On Linux, this should broadly align with XDG-style locations:

* Configuration: `~/.config/modelctl/`
* Persistent data: `~/.local/share/modelctl/`
* Logs and state: `~/.local/state/modelctl/`
* Cache and temporary data: `~/.cache/modelctl/`

The exact paths should be configurable.

modelctl must avoid creating ad hoc files directly under the user’s home root folder.

---

## 5. Setup Requirements

Setup must make it easy to start using modelctl with `llama.cpp` router mode.

During setup, modelctl should discover or ask for:

* The router `.ini` file.
* The active model storage directory.
* The archive model storage directory.
* Existing model directories to scan.
* The modelctl configuration directory.
* The modelctl data directory.
* The modelctl state/log directory.
* The `llama.cpp` server/router binary path if available.
* The command pattern used to start the router.
* The local router endpoint if available.
* The router/server monitoring method.
* The intended usage: manual CLI, Hermes agent, OpenCode, website, dashboard, or mixed use.

If an existing router `.ini` file is found, setup should offer to import it.

If no router `.ini` file is found, setup should offer to create one.

When creating a new router `.ini` file, setup should:

* Ask where the `.ini` file should be stored.
* Scan model storage directories for GGUF files.
* Propose sensible aliases.
* Propose sensible initial runtime settings.
* Create a minimal valid router `.ini` file.
* Store the new `.ini` location in modelctl configuration.
* Show the user how to start `llama.cpp` router mode using that `.ini` file.

Setup should generate clear guidance such as:

* Which `.ini` file was created or imported.
* Which model directories are configured.
* Which archive directory is configured.
* Which modelctl directories are configured.
* Which aliases were detected or created.
* Which command can be used to launch `llama.cpp` with the router `.ini`.
* How to verify router health.
* How to monitor router logs.
* How Hermes agents, OpenCode, or a website should query modelctl rather than guessing the setup.

Setup should support common router/server launch patterns, including:

* Existing systemd service.
* Manual `llama-server` command.
* Docker or container runtime.
* modelctl-managed launch command.
* Existing log file.
* No monitoring configured yet.

Setup must be repeatable. Re-running setup should not destroy existing configuration unless the user explicitly chooses to replace it.

---

## 6. Feature Set

modelctl should support the following command areas.

### Setup and Registry

* `setup` - initialise modelctl from an existing router `.ini` file or create a new one.
* `import` - refresh modelctl’s registry from the router `.ini` file.
* `scan` - inspect configured model storage locations and identify available GGUF files.

### Inspection

* `status` - show concise modelctl/router/model state.
* `list` - list known models, aliases, and relevant metadata.
* `show` - show details for a model, alias, or model file.
* `aliases` - inspect aliases and their model targets.
* `doctor` - inspect modelctl configuration and operational health.
* `rules` - show lifecycle rules, naming rules, monitoring rules, and automation behaviour.

### Lifecycle

* `add` - add a model/router entry.
* `enable` - enable an alias.
* `disable` - disable an alias.
* `archive` - move a model file from active storage to archive storage.
* `restore` - move an archived model file back to active storage.
* `delete` - delete a model file and remove or disable relevant alias/router configuration.
* `recover` - use delete recovery metadata to reconstruct relevant configuration after a model is restored or redownloaded.

### Verification and Evaluation

* `update-check` - compare local model/source state with known metadata.
* `benchmark` - benchmark a model file and runtime settings.
* `classify` - classify model suitability by use case.
* `recommend` - recommend model files, aliases, or runtime settings for a task.

### Router and Runtime Management

* `router status` - show router/server status where configured.
* `router reload` - reload router/server where supported.
* `router restart` - restart router/server where supported.
* `router command` - show the configured command to launch `llama.cpp` router mode.
* `monitor` - show or follow logs for a configured router/server using the appropriate backend.
* Service discovery.
* Post-change verification.
* Machine capability detection.
* Runtime setting recommendation.

### Knowledge and Learning

* Source metadata management.
* Download workflow.
* Model provenance tracking.
* Benchmark history.
* Reliability history.
* Recommendation history.
* Keep/archive/delete rationale.
* Lessons learned from model behaviour.

### Agent and Website Capabilities

* JSON status APIs.
* Agent-readable recommendations.
* Website-readable command outputs.
* Deterministic command outputs.
* Clear lifecycle state.
* Clear router/server state.
* Clear monitoring metadata.
* Clear error and warning structures.

---

## 7. Basic Command Requirements

### setup

`setup` should initialise modelctl.

It should support:

* Importing an existing router `.ini`.
* Creating a new router `.ini` if none exists.
* Configuring model directories.
* Configuring archive directories.
* Configuring modelctl data/state/log directories.
* Scanning for existing GGUF files.
* Proposing initial aliases.
* Configuring router/server launch metadata.
* Configuring router/server monitoring metadata.
* Explaining how to start `llama.cpp` router mode with the `.ini` file.
* Writing only modelctl-owned configuration and state files.

Setup should be friendly enough for a new user and deterministic enough for an agent.

### import

`import` should read the configured router `.ini` and update modelctl’s registry.

It should detect:

* Aliases.
* Model paths.
* Missing model files.
* Duplicate model references.
* Enabled entries.
* Disabled entries.
* Runtime settings.
* Sections or groups in the `.ini`.

`import` should not rewrite the router `.ini` unless explicitly asked through a separate mutation command.

### scan

`scan` should inspect configured model storage locations and find GGUF files.

It should report:

* Model files already referenced in the router `.ini`.
* Model files not yet referenced.
* Model files in active storage.
* Model files in archive storage.
* Possible duplicates.
* Missing files referenced by aliases.

`scan` should support JSON output for agents and websites.

### status

`status` should provide a concise overview of the modelctl environment.

It should report:

* Configured router `.ini` file.
* Configured model storage locations.
* Configured archive storage location.
* Configured modelctl directories.
* Number of known model files.
* Number of aliases.
* Broken aliases.
* Missing model files.
* Archive state.
* Last benchmark or learning status where available.
* Router/server status where safely detectable.
* Monitoring backend where configured.

`status` should be the default command agents can call to understand the environment quickly.

### list

`list` should show known models and aliases.

It should support views such as:

* By model file.
* By alias.
* By lifecycle state.
* By storage location.
* By suitability.
* By benchmark result.
* By recommendation status.

The output should be concise by default and detailed when requested.

### show

`show` should provide detailed information about a model, alias, or model file.

It should include:

* Model file path.
* Alias names.
* Runtime settings.
* Lifecycle state.
* Source metadata.
* Benchmark summary.
* Reliability notes.
* Suitability classification.
* Known warnings.

### aliases

`aliases` should explain how aliases map to model files and runtime settings.

It should support:

* Showing aliases for a specific model.
* Showing aliases pointing to missing files.
* Showing aliases grouped by use case.
* Showing disabled aliases.
* Showing duplicate or redundant aliases.

### doctor

`doctor` should inspect modelctl’s configuration and operational health.

It should check:

* Config file validity.
* Router `.ini` existence.
* Router `.ini` parseability.
* Model storage paths.
* Archive storage path.
* Modelctl data/state/log directories.
* Missing referenced model files.
* Broken aliases.
* Invalid runtime settings where detectable.
* Whether `llama.cpp` router startup guidance can be generated.
* Whether router/server monitoring is configured.
* Whether required modelctl-owned directories exist.

`doctor` should return actionable findings.

### rules

`rules` should display the lifecycle, automation, and monitoring rules used by modelctl.

It should explain:

* Which commands are read-only.
* Which commands are routine mutations.
* Which command requires confirmation.
* How archive behaves.
* How restore behaves.
* How delete behaves.
* How recover behaves.
* Where recovery manifests are stored.
* Where modelctl stores configuration, logs, temporary files, and state.
* How router/server monitoring is configured.
* How agents and websites should use modelctl.

### add

`add` should add a model file to the router `.ini`.

It should support:

* Selecting an existing GGUF file.
* Creating one or more aliases.
* Suggesting alias names.
* Suggesting runtime settings.
* Adding entries to the router `.ini`.
* Updating modelctl registry state.

The user-facing command should be `add`, not `add-entry`.

### enable

`enable` should enable an alias.

It is a routine configuration operation and should not require explicit confirmation by default.

It should:

* Enable only the selected alias.
* Report what changed.
* Preserve unrelated configuration.
* Return deterministic human-readable and JSON-readable output.

### disable

`disable` should disable an alias.

It is a routine configuration operation and should not require explicit confirmation by default.

It should:

* Disable only the selected alias.
* Report what changed.
* Preserve unrelated configuration.
* Return deterministic human-readable and JSON-readable output.

### archive

`archive` should move a model file from active storage to archive storage.

It is a routine reversible storage operation and should not require explicit confirmation by default.

It should preserve aliases by default.

### restore

`restore` should move an archived model file back to active storage.

It is the normal opposite of archive.

It should not require explicit confirmation by default. If it encounters a conflict, it should fail clearly and suggest the explicit command or option needed to resolve the conflict.

### delete

`delete` should delete a model file and remove or disable relevant alias/router configuration.

It is destructive and must require explicit confirmation or an explicit apply flag.

### recover

`recover` should use delete recovery metadata to recreate relevant alias/section configuration after a model has been restored or redownloaded.

It should not restore unrelated router configuration.

### benchmark

`benchmark` should evaluate a model file and runtime settings independently from aliases.

It should help discover the best alias configuration for the current hardware and usage rules.

### classify

`classify` should classify model suitability by use case.

### recommend

`recommend` should recommend aliases, model files, or runtime settings based on task, hardware, benchmark results, reliability, and usage rules.

### update-check

`update-check` should compare local model files with known source metadata.

### monitor

`monitor` should show or follow logs for a configured router/server.

It should hide platform-specific log commands behind a generic modelctl interface.

It should support multiple monitoring backends because users may run `llama.cpp` router mode in different ways.

---

## 8. Primary Use Cases

### Use Case 1 - Manage a llama.cpp Router ini File

The user has or wants a `llama.cpp` router `.ini` file.

modelctl should help:

* Create the `.ini` file.
* Import the `.ini` file.
* Add aliases.
* Enable or disable aliases.
* Detect broken entries.
* Keep the `.ini` readable and useful.
* Explain how to run `llama.cpp` with the `.ini` file.

Success means the user can run router mode without manually maintaining the `.ini` file.

### Use Case 2 - Power a Simple Website

The user may want a simple local website or dashboard to manage models.

modelctl should provide outputs and actions that a website can safely use:

* List models.
* Show model details.
* Enable and disable aliases.
* Archive and restore models.
* Run benchmarks.
* Show recommendations.
* Show router status.
* Show router logs or log metadata.
* Trigger safe routine actions.
* Require confirmation only for model deletion.

Success means the website can call modelctl as the local model management backend.

### Use Case 3 - Active Storage Management

The user may want to move models out of active storage to save space while keeping the ability to bring them back later.

modelctl must support:

* Moving a model from active storage to archive storage.
* Preserving aliases by default during archive.
* Restoring a model back to its original active location.
* Detecting conflicts before restore.
* Keeping router configuration stable unless the user explicitly chooses alias changes.

Success means archive is useful storage management, not a destructive action.

### Use Case 4 - Safe Delete and Recovery

The user may want to delete a model and remove its relevant router configuration while preserving enough metadata to recover later.

modelctl must support:

* Deleting a model file.
* Removing or disabling only relevant aliases and sections.
* Saving a delete recovery manifest.
* Recovering only relevant aliases/sections later.
* Preserving unrelated router changes made after delete.

Success means delete is destructive but still well-managed.

### Use Case 5 - Hermes Agent Operations

Hermes agents need deterministic model operations.

modelctl must allow agents to:

* Query model state using JSON.
* Determine whether a model is active, archived, missing, broken, suitable, or unsuitable.
* Select the right alias/runtime settings for a task.
* Avoid guessing paths, endpoints, service names, aliases, or model capability.
* Perform low-risk operations autonomously.
* Require user approval only for model deletion.
* Report actionable errors to the user.

Success means Hermes agents can manage model operations without brittle assumptions.

### Use Case 6 - OpenCode and Coding Agent Reliability

OpenCode and similar agents need reliable model selection for coding workflows.

modelctl must help decide:

* Which alias/runtime settings are suitable for build or tool-using work.
* Which alias/runtime settings are better for planning or reasoning.
* Which model/settings are only for long-context diagnostics.
* Which models have previously corrupted output, failed JSON generation, or broken tool calls.
* Which runtime settings have enough context headroom for the requested task.

Success means local coding work can continue when cloud credits are unavailable.

### Use Case 7 - Router Monitoring and Diagnosis

The user wants to inspect router/server logs without remembering the underlying platform command.

modelctl should help:

* Tail logs from a systemd service.
* Tail logs from a configured log file.
* Tail logs from a container.
* Inspect logs for a modelctl-managed router process.
* Show recent log lines.
* Follow logs live.
* Show the monitoring backend being used.
* Report clear errors when monitoring is not configured.

Success means the user can run one generic modelctl command instead of remembering commands such as:

* `journalctl -u <service> -f`
* `tail -f <log-file>`
* `docker logs -f <container>`

### Use Case 8 - Active Model Hygiene

The user does not want an ever-growing, confusing list of models and aliases.

modelctl must help maintain a small, curated active set:

* Keep useful models active.
* Archive duplicates and weak models.
* Detect stale aliases.
* Detect missing files.
* Recommend archive candidates based on redundancy, reliability, benchmark results, and usage.

Success means the router remains understandable and operational.

### Use Case 9 - Evidence-Based Model Choice

The user wants model choices to improve over time based on evidence.

modelctl must capture or support:

* Benchmarks.
* Reliability observations.
* Context stability findings.
* Tool-call stability findings.
* Keep/archive/delete decisions.
* Known model strengths and failure modes.
* Recommended alias configurations.

Success means model choice becomes evidence-based.

---

## 9. Core Product Principles

### Make the User’s Life Easier

The purpose of modelctl is to reduce friction.

modelctl should automate repetitive model management work, avoid unnecessary prompts, and make safe decisions deterministic.

It should not ask for confirmation for routine actions.

### Automation with Minimal Friction

The product should distinguish between:

* Read-only actions.
* Routine reversible actions.
* Destructive actions.

Routine reversible actions should be automatable.

The normal action that requires confirmation is deleting a model.

### Deterministic by Default

Commands must produce predictable, repeatable results.

The same input state should produce the same output state unless external state has changed.

### JSON-First for Agents and Websites

Human-readable output is useful, but machine-readable output is essential.

Commands intended for automation must provide stable JSON output.

### Surgical Lifecycle Operations

Lifecycle operations must affect only the relevant model file, aliases, sections, and metadata.

modelctl must not use whole-router restoration as the default way to undo archive or delete actions.

### Router-Mode Specificity

modelctl is specifically designed around `llama.cpp` router mode.

It must understand that the `.ini` file is central to the system.

When helping the user or an agent, modelctl should always be able to answer:

* Which `.ini` file is being managed?
* Which aliases are defined in it?
* Which GGUF files do they point to?
* How should `llama.cpp` be started with this `.ini` file?
* How can the running router/server be monitored?

### Status Tracking Belongs Elsewhere

This requirements document describes the intended feature set.

Feature status, roadmap progress, backlog, and implementation state should live in separate documents or issue trackers.

### Documentation-Driven Development

New behaviour should be documented before or alongside implementation.

A code change without corresponding requirement, safety, or usage documentation is incomplete.

---

## 10. Safety and Automation Requirements

### Read-Only Commands

Read-only commands must not modify:

* Router `.ini` files.
* Model files.
* Registry files.
* Metadata files.
* Runtime service state.

### Routine Mutating Commands

Routine mutating commands may apply directly when their behaviour is reversible, scoped, and deterministic.

Routine mutating commands include:

* `add`
* `enable`
* `disable`
* `archive`
* `restore`
* `recover`
* metadata updates where data loss is not possible
* router reload or restart where the requested action is explicit

These commands should:

* Report what changed.
* Limit changes to relevant files, aliases, sections, and metadata.
* Preserve unrelated configuration.
* Return deterministic human-readable and JSON-readable output.

They do not require explicit confirmation by default.

### Destructive Commands

`delete` is destructive and must require explicit confirmation or an explicit apply flag.

Before delete applies, modelctl must show:

* Model file to be deleted.
* Relevant aliases/sections to be removed or disabled.
* Recovery manifest path.
* Source metadata available for future recovery.
* Whether the model can reasonably be recovered later.

### Conflict Handling

A command should fail clearly rather than ask repeated questions when it encounters a conflict.

Examples:

* Restore target file already exists.
* Alias already points to a different model.
* Recovery manifest is incomplete.
* Router `.ini` cannot be parsed.
* Configured directory is unavailable.
* Monitoring backend is not configured.
* Configured service, container, or log file cannot be found.

The user or agent can then choose a more explicit command or override where appropriate.

### Agent Safety Rules

Agents must not guess:

* Model suitability.
* Router endpoints.
* Service names.
* Model aliases.
* File locations.
* Monitoring backend.
* Whether a command is safe to mutate state.

Agents should query modelctl and act on deterministic output.

---

## 11. Domain Model

### Router ini File

The `llama.cpp` router configuration file managed by modelctl.

It contains aliases and runtime settings used by router mode.

### Model File

A local GGUF model file with metadata such as path, size, quantisation, family, parameter count, source, and known status.

### Alias

A router-facing name that points to a model file and runtime settings.

### Section

A logical group or configuration section in the router `.ini` file.

### Runtime Settings

The settings attached to an alias or benchmark run, such as context size, output limit, sampling settings, GPU layers, cache settings, and parallelism.

### Registry

The local modelctl record of known models, aliases, metadata, status, and decisions.

### Active Storage

The directory or directories where active models are stored.

### Archive Storage

The directory or directories where archived models are stored.

### Machine Capability Record

A description of available hardware and runtime capability on a host.

### Reliability Record

Evidence about how a model and runtime settings behave under real workloads.

### Archive Metadata

A record of file movement from active storage to archive storage, with enough information to restore the file later.

### Delete Recovery Manifest

A JSON manifest created before delete applies.

It contains only relevant model, alias, section, source, and recovery metadata needed to reconstruct deleted model configuration later.

### Router Server

The running `llama.cpp` router/server instance using the managed `.ini` file.

### Monitoring Backend

The configured method used to inspect router/server logs.

Examples include:

* systemd service logs
* file logs
* container logs
* modelctl-managed process logs
* configured read-only log command

### Learning Log

A record of observed outcomes, decisions, and rationale.

---

## 12. Lifecycle Model

modelctl separates reversible storage management from destructive lifecycle management.

The lifecycle concepts are:

* `archive` - move a model from active storage to archive storage.
* `restore` - move an archived model back to active storage.
* `delete` - remove a model file and relevant alias/router configuration.
* `recover` - use delete recovery metadata to reconstruct relevant configuration after the model is restored or redownloaded.

Archive/restore and delete/recover must be surgical.

They must operate only on:

* The relevant model file.
* The relevant aliases.
* The relevant sections.
* The relevant metadata.

They must preserve unrelated router changes.

---

## 13. Archive Requirements

Archive is a reversible storage-management operation.

Archive should:

* Move a model file from active storage to archive storage.
* Preserve alias/router configuration by default.
* Offer an explicit option to disable affected aliases if desired.
* Disable only aliases directly associated with the archived model when that option is used.
* Write movement metadata sufficient for restore.
* Report the exact file movement and alias impact.
* Preserve unrelated router configuration.

Archive must not:

* Delete the model file permanently.
* Remove unrelated aliases.
* Rewrite unrelated router configuration.
* Disable aliases by default.

Archive does not require explicit confirmation by default.

---

## 14. Restore Requirements

Restore is the opposite of archive.

The preferred user-facing command is:

* `restore`

An optional alias may be added later:

* `unarchive`

Restore should:

* Move an archived model back to its original active storage path.
* Preserve unrelated router configuration.
* Re-enable affected aliases only if they were disabled by the archive operation and restore metadata confirms it.
* Detect conflicts before applying.
* Report all changes.

Restore must not:

* Replace the full router configuration by default.
* Erase unrelated changes made after archive.
* Recreate unrelated aliases.

Restore does not require explicit confirmation by default.

If restore encounters a conflict, it should fail clearly and explain the explicit command or option needed to resolve the conflict.

---

## 15. Delete Requirements

Delete is destructive lifecycle management.

Delete should:

* Remove the model file from managed storage.
* Remove or disable only the relevant aliases/sections.
* Create a JSON recovery manifest before applying destructive changes.
* Save only the affected alias/section configuration, not the whole router configuration.
* Include model source metadata where known.
* Include model filename, size, hash, and redownload source where available.
* Show the exact files, aliases, sections, and recovery manifest before applying.

Delete must not:

* Remove unrelated aliases.
* Rewrite unrelated router configuration.
* Destroy useful recovery metadata.

Delete requires explicit confirmation or an explicit apply flag.

---

## 16. Recover Requirements

Recover uses a delete recovery manifest.

Recover should:

* Read recovery metadata created by delete.
* Verify whether the model file exists again or has been redownloaded.
* Restore only the relevant aliases/sections.
* Preserve unrelated router changes made after delete.
* Detect conflicts before applying.
* Report what cannot be recovered automatically.

Recover must not:

* Restore the whole old router configuration by default.
* Overwrite unrelated current aliases.
* Assume that the model file exists unless verified.
* Hide conflicts from the user or agent.

Recover does not require explicit confirmation by default.

If recover encounters a conflict, it should fail clearly and explain the explicit command or option needed to resolve the conflict.

---

## 17. Alias and Runtime Setting Strategy

Aliases should be organised by use case rather than only by model name.

Recommended alias purposes include:

* Coding/tool use.
* Reasoning/planning.
* Fast chat.
* Long-context testing.
* Emergency or recovery use.
* Experimental testing.
* Auxiliary/background tasks.

Rules:

* Coding/tool-use aliases prioritise deterministic tool reliability over maximum context.
* Long-context-test aliases are diagnostic and should not be used for routine build work.
* Alias purpose must be visible to humans and agents.
* A model can have multiple aliases with different runtime settings.
* Benchmarking should help decide the best runtime settings for each alias purpose.

---

## 18. Model Reliability and Context Management

Configured context size is not proof of reliable context size.

modelctl must track practical reliability, especially for agent workflows where a model must produce valid JSON, tool calls, patches, or structured output.

Reliability metadata should include:

* Maximum reliable chat/reasoning context.
* Maximum reliable tool-using context.
* Recommended maximum output tokens.
* JSON reliability.
* Tool-call reliability.
* Structured-output reliability.
* Repeated-token or corruption incidents.
* Successful reliability tests.
* Failed reliability tests.
* Failure mode.
* Reproduction conditions.
* Mitigation applied.
* Post-mitigation outcome.
* Compaction survivability.

Context headroom tracking should include:

* Configured context.
* Current prompt tokens.
* Output token limit.
* Remaining context.
* Remaining context minus output budget.

A model and runtime setting combination should be considered risky when remaining context is below output budget plus a safety margin.

Reliability should be assessed per model, per machine, per runtime settings, and per workload type.

---

## 19. Benchmarking Requirements

Benchmarking is alias-independent.

The purpose of benchmarking is to evaluate a model file and runtime settings so modelctl can recommend the best alias configuration for the current hardware and intended usage.

Benchmarking should track:

* Prompt throughput.
* Generation throughput.
* Memory usage.
* Context reliability.
* Tool-call reliability.
* Compaction survivability.
* Runtime settings.
* Hardware capability.
* Quantisation.
* Context size.
* Output limit.
* Date/time of benchmark.
* Benchmark command used.

Benchmarking should support:

* Storing benchmark results.
* Comparing results over time.
* Comparing runtime settings for the same model.
* Comparing models for the same task type.
* Feeding benchmark history into recommendations.
* Recommending alias runtime settings based on evidence.

A benchmark result should be useful to both humans and agents.

---

## 20. Model Classification Requirements

Model classification should cover suitability for:

* Coding.
* Reasoning.
* Summarisation.
* Agent/tool use.
* Fast chat.
* Long-context testing.
* Experimental use.
* Archive candidacy.

Classification metadata should include:

* Suitability score.
* Confidence score.
* Known strengths.
* Known failure modes.
* Recommended maximum output.
* Recommended runtime settings.
* Known hardware constraints.
* Known context constraints.

Classification should be evidence-based where possible and clearly marked as inferred where evidence is limited.

---

## 21. Recommendation Engine Requirements

Recommendations should consider:

* Task type.
* Hardware capability.
* Runtime settings.
* Reliability history.
* Benchmark history.
* Context needs.
* Output needs.
* Tool-call needs.
* Active model hygiene.
* User-defined preferences.

Recommendation types should include:

* Task-based recommendations.
* Hardware-aware recommendations.
* Reliability-aware recommendations.
* Benchmark-aware recommendations.
* Active-model hygiene recommendations.
* Archive candidate recommendations.
* Alias/runtime-setting recommendations.

Recommendations should favour a small curated active model set, not the maximum number of installed models.

A recommendation must explain its rationale in both human-readable and JSON-compatible form.

---

## 22. Router Management Requirements

Router management should include:

* Router status.
* Router reload.
* Router restart.
* Router health verification.
* Service discovery.
* Post-change verification.
* Safe restart and reload behaviour.
* Current model availability checks.
* Guidance on how to launch `llama.cpp` router mode with the configured `.ini` file.

Router reload and restart are operational actions.

They should not require approval every time, but they must be clearly reported and must fail clearly when the router state is invalid.

Agents should not guess router endpoints or service names.

modelctl should provide this information deterministically from configuration.

---

## 23. Router Monitoring Requirements

modelctl should provide a `monitor` command to make router/server log inspection simple and platform-independent.

The purpose of `monitor` is to let a user, agent, or website inspect runtime logs for a configured `llama.cpp` router/server without remembering the underlying command.

Examples:

* If the router is configured as a systemd service, the user should not need to remember `journalctl -u <service> -f`.
* If the router writes to a log file, the user should not need to remember the log path.
* If the router runs in a container, the user should not need to remember the container name or `docker logs` command.
* If the router is launched by modelctl, the user should be able to monitor the modelctl-managed log.

### monitor

`monitor` should inspect or follow logs for a configured router/server.

It should support:

* Selecting a configured router/server.
* Showing recent log lines.
* Following logs live.
* Showing service status context where available.
* Showing the backend being used.
* Showing the command being used internally where appropriate.
* Supporting human-readable output.
* Supporting JSON-friendly metadata output.
* Returning clear errors when no monitor source is configured.

Example command shapes:

* `modelctl monitor`
* `modelctl monitor router`
* `modelctl monitor router --follow`
* `modelctl monitor router --lines 200`
* `modelctl monitor router --since "10 minutes ago"`

### Monitor Backends

modelctl should support multiple monitoring backends because users may run `llama.cpp` router mode in different ways.

Supported backend types should include:

* `systemd` - follow logs using the configured service name.
* `file` - follow a configured log file.
* `docker` or `container` - follow logs for a configured container.
* `process` - inspect a known modelctl-launched process where supported.
* `command` - run a configured safe read-only log command.
* `none` - no monitoring configured.

Backend configuration should live in modelctl configuration, not in ad hoc scripts or the user’s home root folder.

### Setup Integration for Monitoring

During setup, modelctl should ask how the router is normally run.

Setup should support:

* Existing systemd service.
* Manually launched `llama-server`.
* Docker/container runtime.
* modelctl-managed launch command.
* Existing log file.
* No monitoring for now.

If the user selects systemd, setup should store the service name.

If the user selects file logging, setup should store the log file path.

If the user selects container logging, setup should store the container name or identifier.

If the user selects modelctl-managed launch, modelctl should store logs under the configured modelctl state/log directory.

Setup should also show the equivalent manual command for transparency, for example:

* `journalctl -u <service> -f`
* `tail -f <log-file>`
* `docker logs -f <container>`

### Monitor Safety

`monitor` is read-only.

It must not:

* Restart services.
* Reload the router.
* Kill processes.
* Modify router configuration.
* Modify model files.
* Modify aliases.

If the user wants operational actions such as restart or reload, those should be separate commands.

### Agent and Website Use

Hermes agents, OpenCode, and simple websites should be able to use `monitor` to help diagnose router issues.

The command should make it easy to answer:

* Is the router producing errors?
* Did the model load successfully?
* Is the router listening?
* Are requests reaching the router?
* Are context or memory errors appearing?
* Did a model fail to load because of a bad path or invalid settings?

For automation, `monitor` should expose metadata such as:

* Backend type.
* Selected router/server.
* Service/container/log identifier.
* Whether follow mode is active.
* Number of lines requested.
* Internal command used.
* Errors encountered.

The raw log stream may remain plain text, but the selected backend and monitoring configuration should be machine-readable.

---

## 24. Active Model Hygiene Requirements

Active model hygiene should keep the router useful, stable, and understandable.

Hygiene checks should include:

* Duplicate detection.
* Stale alias detection.
* Unused model detection.
* Missing GGUF detection.
* Broken alias detection.
* Redundant alias detection.
* Archive recommendations.
* Active-set minimisation.

The target state is a small, curated active set with archived models available for recovery, comparison, or experimentation.

Hygiene recommendations should be actionable and automatable.

---

## 25. Source Metadata and Update Requirements

modelctl should track where models came from and whether local files are up to date.

Source metadata should include:

* Source repository or provider.
* Model filename.
* Expected size.
* Expected hash where available.
* Quantisation.
* Download date where known.
* Local file status.
* Update availability.
* Trust level of metadata.

Update-check workflows should distinguish:

* Confirmed match.
* Possible update.
* Missing source metadata.
* Local file missing.
* Hash mismatch.
* Size mismatch.
* Unsupported source.

Update workflows must not replace a working local model without clear user intent.

---

## 26. Learning Log Requirements

modelctl should maintain or support a learning log so model decisions improve over time.

The learning log should capture:

* Benchmark history.
* Recommendation history.
* Reliability observations.
* Decisions made.
* Rationale tracking.
* Lessons learned.
* Keep/archive/delete decisions.
* Model suitability notes.
* Failed experiments.
* Successful mitigations.
* User overrides.

The learning log should be useful to both humans and agents.

It should make future recommendations more grounded and reduce repeated mistakes.

---

## 27. Agent and Website Integration Requirements

modelctl should support Hermes agents, OpenCode, simple websites, and future local clients through deterministic command outputs.

Integration requirements:

* JSON APIs.
* Deterministic outputs.
* Status consumption.
* Recommendation consumption.
* Clear error states.
* Machine-readable warnings.
* Machine-readable lifecycle state.
* Machine-readable router/server state.
* Machine-readable monitoring metadata.
* Machine-readable model suitability.
* Website-friendly command outputs.

Clients should query modelctl instead of guessing:

* Model suitability.
* Service names.
* Endpoints.
* Model aliases.
* Runtime settings.
* Monitoring backend.
* Whether a mutation is safe.

OpenCode-specific requirements should remain general where possible so modelctl can support other clients later.

---

## 28. Command Output Requirements

Human-readable output should be concise and useful.

JSON output should be stable and suitable for automation.

JSON output should include where relevant:

* Command name.
* Status.
* Success/failure.
* Affected models.
* Affected aliases.
* Affected sections.
* Affected files.
* Lifecycle state.
* Router/server state.
* Monitoring backend.
* Warnings.
* Errors.
* Recovery guidance.
* Recommendation rationale.
* Machine metadata.
* Runtime settings.

Errors should be actionable.

They should explain what failed, why it matters, and what the user or agent should do next.

---

## 29. Configuration Requirements

modelctl should avoid hard-coded local assumptions.

Configuration should support:

* Router `.ini` file location.
* Model storage locations.
* Archive location.
* Registry location.
* Modelctl configuration directory.
* Modelctl data directory.
* Modelctl log/state directory.
* Modelctl cache/temp directory.
* Recovery manifest directory.
* Benchmark result directory.
* Machine capability record.
* Runtime settings.
* Preferred aliases.
* Router/server launch command.
* Router/server endpoint.
* Router/server monitoring backend.
* JSON output preferences where useful.

Configuration should be inspectable and validated by `doctor`.

Agents and websites must not infer configuration by reading unrelated files when modelctl can provide it directly.

---

## 30. User Personas

### Manual User

Needs:

* Quick CLI inspection.
* Minimal unnecessary confirmations.
* Clear errors.
* Simple lifecycle operations.
* A way to understand which models are worth keeping.
* A way to manage the router `.ini` file without editing it by hand.
* A way to monitor router logs without remembering platform-specific commands.

### Hermes Agent

Needs:

* Deterministic JSON.
* Status and suitability data.
* Model recommendations.
* Recovery paths.
* Monitoring access.
* No requirement to infer local configuration manually.
* A reliable source of truth for model operations.
* Permission to perform routine operations autonomously.

### OpenCode or Coding Agent

Needs:

* Reliable coding/tool-use alias selection.
* Tool-call reliability data.
* Context headroom guidance.
* Stable local model operations when cloud credits are unavailable.
* Model recommendations that avoid known corruption-prone configurations.
* Monitoring output when the router or model server fails.

### Website or Dashboard

Needs:

* Fast status output.
* Safe action endpoints.
* List/show/recommend outputs.
* Archive/restore actions.
* Benchmark actions.
* Monitoring views.
* Delete confirmation workflow.
* Clear result messages.

### Maintainer/Developer

Needs:

* Clear product requirements.
* Testable behaviour.
* Maintainable command structure.
* Documentation before risky features.
* Separate status tracking outside this requirements document.

---

## 31. Acceptance Criteria

A feature is not complete unless:

* The requirement is documented.
* Read-only vs routine-mutating vs destructive behaviour is clear.
* JSON behaviour is defined where clients may use it.
* Tests exist for safety-critical paths.
* The feature avoids hard-coded local assumptions.
* The feature gives actionable errors.
* The feature stores its logs, temporary files, configuration, and recovery files in appropriate modelctl-owned locations.

A routine mutating feature is not complete unless:

* Affected files/models/aliases/sections are reported.
* Unrelated configuration is preserved.
* Failure states are handled.
* JSON output is available where clients may use it.
* It does not require unnecessary user confirmation.

A destructive feature is not complete unless:

* Explicit confirmation or apply mode exists.
* Affected files/models/aliases/sections are shown before deletion.
* Recovery metadata is created where practical.
* Failure states are handled.
* Recovery guidance exists where practical.

An agent-facing or website-facing feature is not complete unless:

* Output is deterministic.
* JSON is stable.
* Errors are machine-readable.
* Low-risk automation is possible without unnecessary human approval.

A lifecycle feature is not complete unless:

* It operates surgically on relevant models, aliases, sections, and metadata.
* It preserves unrelated router configuration.
* It has conflict detection where current state may have changed.
* It distinguishes archive/restore from delete/recover.

A monitoring feature is not complete unless:

* It supports at least one configured backend.
* It reports the backend being used.
* It can show recent logs.
* It can follow logs where the backend supports it.
* It stores monitoring configuration in modelctl-owned configuration.
* It does not mutate router/server state.

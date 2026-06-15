# modelctl Requirements

## 1. Product Vision

modelctl is the deterministic local model operations layer for a home/local AI system.

It manages llama.cpp router model configuration, model lifecycle operations, model validation, benchmarking, reliability tracking, recommendation logic, and agent-facing model selection.

The product exists because local AI systems become fragile when humans or agents rely on manual memory, ad hoc aliases, undocumented model choices, or guessing. modelctl should make local model operations inspectable, repeatable, safe, and suitable for automation.

The long-term goal is:

* Buster/Hermes acts as the natural-language orchestration layer.
* OpenCode and other coding agents act as task-specific clients.
* modelctl acts as the deterministic source of truth for local model state, suitability, safety, and operational decisions.

Any capable human or AI agent should be able to read this document and understand what modelctl is supposed to become.

---

## 2. Product Mission

modelctl must help the user answer and automate questions such as:

* What models are available?
* Which models are active in the router?
* Which aliases point to which files?
* Which models are safe for coding agents?
* Which models are safe for long-context planning?
* Which models are reliable for tool calls and JSON output?
* Which models should be archived?
* Which models are missing, duplicated, stale, or broken?
* Which model should Buster or OpenCode use for this task?
* Is the router healthy?
* Can the system recover if a model is archived by mistake?
* What has been learned from previous benchmarks and reliability tests?

modelctl should reduce operational uncertainty, protect fallback capability, and provide clear command-line and JSON outputs for both humans and agents.

---

## 3. Current Implemented Command Surface

The current CLI already provides a useful foundation. The implemented command surface should be treated as the baseline and protected from regression.

### Setup and Registry

* `setup` - import an existing router configuration and create minimal modelctl configuration and registry data.
* `import` - refresh the registry from the configured router file.
* `scan` - inspect known model locations and identify available model files.

### Inspection

* `list` - list known models.
* `show` - show model details.
* `aliases` - inspect aliases.
* `doctor` - inspect configuration and operational health.
* `rules` - inspect configured rules or safety constraints.

### Lifecycle

* `add-entry` - add a model/router entry.
* `enable` - enable a model/alias.
* `disable` - disable a model/alias.
* `delete` - preview or apply deletion of a model.
* `archive` - preview or apply archiving of a model.
* `rollback` - preview or apply archive rollback recovery.

### Verification

* `update-check` - compare local model/source state with known metadata where available.
* `benchmark` - run model performance benchmarking.

The implemented command list must remain accurate. When a new command is added, this section must be updated in the same change or the change is incomplete.

---

## 4. Planned Capabilities

The following capabilities are required for the product vision but may not all exist yet. They must not be described elsewhere as implemented until they actually are.

### Planned Router Capabilities

* Router status
* Router reload
* Router restart
* Router health verification
* Service discovery
* Post-change verification

### Planned Recommendation Capabilities

* Task-based model recommendations
* Hardware-aware model recommendations
* Reliability-aware model recommendations
* Benchmark-aware model recommendations
* Active-model hygiene recommendations
* Fallback recommendations

### Planned Classification Capabilities

* Model use-case classification
* Suitability scoring
* Confidence scoring
* Failure-mode metadata
* Recommended profile/mode per model

### Planned Metadata and Lifecycle Capabilities

* Source metadata management
* Download workflow
* Model provenance tracking
* Active model hygiene workflows
* Duplicate/stale/missing model detection
* Machine profiles
* Role/profile-based alias selection

### Planned Knowledge Capabilities

* Learning log
* Benchmark history
* Reliability history
* Recommendation history
* Keep/archive/delete rationale
* Lessons learned from model behaviour

### Planned Agent Capabilities

* Richer JSON status APIs
* Agent-readable recommendation output
* Agent-readable safety status
* Agent-readable model reliability summaries

---

## 5. Primary Use Cases

### Use Case 1 - Safe Manual Model Management

The user wants to manage local GGUF models without manually editing router configuration files.

modelctl must allow the user to:

* Inspect available models and aliases.
* Add, enable, disable, archive, delete, or rollback model entries.
* Preview changes before applying them.
* Understand exactly what files, aliases, and configuration entries will be affected.
* Recover from accidental archive operations where possible.

Success means the user can manage models confidently without damaging the router setup or losing fallback capability.

### Use Case 2 - Buster/Hermes Model Operations

Buster and Hermes need deterministic model operations.

modelctl must allow agents to:

* Query model state using JSON.
* Determine whether a model is active, archived, missing, broken, or suitable.
* Select the right profile for a task.
* Avoid guessing paths, endpoints, service names, aliases, or model capability.
* Avoid unsafe mutations unless explicitly approved.
* Report actionable errors to the user.

Success means Buster can operate like a Chief of Staff AI without making brittle assumptions about the local AI stack.

### Use Case 3 - OpenCode and Coding Agent Reliability

OpenCode and similar agents need reliable model selection for coding workflows.

modelctl must help decide:

* Which model/profile is safe for Build mode or tool-using work.
* Which model/profile is better for planning or reasoning.
* Which model/profile is only for long-context diagnostics.
* Which models have previously corrupted output, failed JSON generation, or broken tool calls.
* Which profile has enough context headroom for the requested task.

Success means local coding work can continue when cloud credits are unavailable, without repeated corruption or tool-call failures.

### Use Case 4 - Active Model Hygiene

The user does not want an ever-growing, confusing list of models and aliases.

modelctl must help maintain a small, curated active set:

* Keep the best models active.
* Archive duplicates and weak models.
* Detect stale aliases.
* Detect missing files.
* Protect fallback models.
* Recommend archive candidates based on redundancy, reliability, and usage.

Success means the router remains understandable and operational rather than becoming a graveyard of forgotten experiments.

### Use Case 5 - Model Evaluation and Learning

The user wants model choices to improve over time based on evidence.

modelctl must capture or support:

* Benchmarks.
* Reliability observations.
* Context stability findings.
* Tool-call stability findings.
* Keep/archive/delete decisions.
* Rationale for recommendations.
* Known model strengths and failure modes.

Success means model selection becomes evidence-based rather than dependent on memory or vibes.

---

## 6. Core Product Principles

### Deterministic by Default

Commands must produce predictable, repeatable results. The same input state should produce the same output state unless external state has changed.

### Preview Before Mutation

Any command that mutates files, router configuration, registry data, or model state must support preview-first behaviour. Applying a mutation must require explicit confirmation or an explicit apply flag.

### JSON-First for Agents

Human-readable output is useful, but agent-readable output is essential. Commands intended for automation must provide stable JSON output.

### Safety Over Convenience

modelctl should prefer refusing or warning over performing ambiguous or risky actions.

### Fallback Protection

modelctl must protect fallback capability. A workflow that disables, archives, deletes, or breaks all viable fallback models should be blocked or require an explicit high-risk override.

### Current vs Planned Honesty

The documentation must clearly distinguish implemented behaviour from planned capabilities. It must not imply that planned commands already exist.

### Documentation-Driven Development

New behaviour should be documented before or alongside implementation. A code change without corresponding requirement, safety, or usage documentation is incomplete.

---

## 7. Safety Requirements

### Read-Only Commands

Read-only commands must not modify:

* Router configuration files.
* Model files.
* Registry files.
* Metadata files.
* Logs, except where explicitly documented.
* Runtime service state.

### Mutating Commands

Mutating commands must:

* Show what will change.
* Show affected files.
* Show affected aliases.
* Show affected models.
* Show risk level where relevant.
* Require explicit apply or confirmation.
* Provide recovery guidance where possible.

### High-Risk Operations

High-risk operations include:

* Deleting model files.
* Archiving active models.
* Disabling active or fallback aliases.
* Editing router configuration.
* Restarting or reloading router services.
* Changing source metadata.
* Recommending removal of fallback models.

High-risk operations must have stronger guardrails than low-risk inspection commands.

### Agent Safety Rules

Agents must not guess:

* Model suitability.
* Router endpoints.
* Service names.
* Model aliases.
* File locations.
* Fallback availability.
* Whether a command is safe to mutate state.

Agents should query modelctl and act on deterministic output.

---

## 8. Domain Model

modelctl should reason about these product entities.

### Model File

A local GGUF model file with metadata such as path, size, quantisation, family, parameter count, source, and known status.

### Alias

A router-facing name that points to a model file and runtime configuration.

### Profile

A usage-oriented configuration or alias strategy. Examples include build-safe, plan, fallback, long-context-test, auxiliary, and sandbox.

### Registry

The local modelctl record of known models, aliases, metadata, status, and decisions.

### Router Configuration

The configuration file or files used by the local llama.cpp router.

### Machine Profile

A description of available hardware and runtime capability on a host.

### Runtime Profile

A description of runtime parameters such as context size, output limit, sampling settings, GPU layers, cache settings, and parallelism.

### Reliability Record

Evidence about how a model/profile behaves under real workloads.

### Learning Log

A record of observed outcomes, decisions, and rationale.

---

## 9. Alias and Profile Separation

Aliases should be organised by use case rather than only by model name.

Recommended profile types:

* `build-safe` - tool-using work where JSON, patching, and command discipline matter.
* `plan` - reasoning and analysis work with moderate context.
* `long-context-test` - diagnostic use only.
* `fallback` - recovery and emergency use.
* `auxiliary` - lightweight background or helper tasks.
* `sandbox` or `experimental` - testing without production expectations.

Rules:

* Build-safe profiles prioritise deterministic tool reliability over maximum context.
* Long-context-test profiles must not be used for production build work.
* Fallback profiles must remain available.
* Profile purpose must be visible to humans and agents.
* A model can have multiple profiles with different runtime settings.

---

## 10. Model Reliability and Context Management

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

A model/profile should be considered risky when remaining context is below output budget plus a safety margin.

Reliability should be assessed per model, per profile, per machine, and per workload type.

---

## 11. Benchmarking Requirements

`benchmark` exists today. It should become more than a speed test.

Benchmarking should track:

* Prompt throughput.
* Generation throughput.
* Memory usage.
* Context reliability.
* Tool-call reliability.
* Compaction survivability.
* Runtime settings.
* Machine profile.
* Runtime profile.
* Quantisation.
* Context size.
* Output limit.
* Date/time of benchmark.
* Benchmark command used.

Planned benchmark enhancements:

* Store benchmark results.
* Compare results over time.
* Compare profiles for the same model.
* Compare models for the same task type.
* Use benchmark history in recommendations.

A benchmark result should be useful to a human and to an agent.

---

## 12. Model Classification Requirements

Model classification scoring is a planned capability unless already implemented.

Classification should cover suitability for:

* Coding.
* Reasoning.
* Summarisation.
* Agent/tool use.
* Fast chat.
* Fallback.
* Long-context testing.
* Experimental use.
* Archive candidacy.

Classification metadata should include:

* Suitability score.
* Confidence score.
* Known strengths.
* Known failure modes.
* Recommended maximum output.
* Recommended profile or mode.
* Known hardware constraints.
* Known context constraints.

Classification should be evidence-based where possible and clearly marked as inferred where evidence is limited.

---

## 13. Recommendation Engine Requirements

The recommendation engine is a planned capability unless already implemented.

Recommendations should consider:

* Task type.
* Hardware profile.
* Runtime profile.
* Reliability history.
* Benchmark history.
* Context needs.
* Output needs.
* Tool-call needs.
* Fallback availability.
* Active model hygiene.
* User-defined preferences.

Recommendation types should include:

* Task-based recommendations.
* Hardware-aware recommendations.
* Reliability-aware recommendations.
* Benchmark-aware recommendations.
* Active-model hygiene recommendations.
* Archive candidate recommendations.
* Fallback recommendations.

Recommendations should favour a small curated active model set, not the maximum number of installed models.

A recommendation must explain its rationale in both human-readable and JSON-compatible form.

---

## 14. Router Management Requirements

Router lifecycle commands are planned unless already implemented.

Router management should include:

* Router status.
* Router reload.
* Router restart.
* Router health verification.
* Service discovery.
* Post-change verification.
* Safe restart and reload rules.
* Current model availability checks.

Router operations must protect:

* Main model availability.
* Auxiliary model availability.
* Fallback model availability.

Agents should not guess router endpoints or service names. modelctl should provide this information deterministically from configuration.

---

## 15. Active Model Hygiene Requirements

Active model hygiene should keep the router useful, stable, and understandable.

Hygiene checks should include:

* Duplicate detection.
* Stale alias detection.
* Unused model detection.
* Missing GGUF detection.
* Broken alias detection.
* Redundant profile detection.
* Archive recommendations.
* Fallback protection.
* Active-set minimisation.
* Prevention against disabling all viable fallback models.

The target state is a small, curated active set with archived models available for recovery, comparison, or experimentation.

Hygiene recommendations must be preview-first and should never silently remove capability.

---

## 16. Source Metadata and Update Requirements

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

Update workflows must never replace a working fallback model without safe preview and recovery guidance.

---

## 17. Rollback and Recovery Requirements

Lifecycle operations should support recovery where practical.

Rollback requirements include:

* Preview rollback actions.
* Restore archived model files where possible.
* Restore router aliases where possible.
* Report missing recovery metadata.
* Report partial recovery.
* Avoid overwriting newer files without explicit confirmation.
* Preserve fallback capability during recovery.

Archive and rollback operations should produce enough metadata for humans and agents to understand what happened and how to recover.

---

## 18. Learning Log Requirements

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

## 19. Agent Integration Requirements

modelctl should support Buster, Hermes, OpenCode, and future local agents through deterministic command outputs.

Agent integration requirements:

* JSON APIs.
* Deterministic outputs.
* Status consumption.
* Recommendation consumption.
* Clear error states.
* Safe defaults.
* No hidden mutations.
* Machine-readable warnings.
* Machine-readable risk levels.
* Machine-readable planned vs implemented capability status.

Agents should query modelctl instead of guessing:

* Model suitability.
* Service names.
* Endpoints.
* Model aliases.
* Runtime profiles.
* Fallback availability.
* Whether a mutation is safe.

OpenCode-specific requirements should remain general where possible so modelctl can support other agent clients later.

---

## 20. Command Output Requirements

Human-readable output should be concise and useful.

JSON output should be stable and suitable for automation.

JSON output should include where relevant:

* Command name.
* Status.
* Success/failure.
* Affected models.
* Affected aliases.
* Affected files.
* Risk level.
* Planned vs applied state.
* Warnings.
* Errors.
* Recovery guidance.
* Recommendation rationale.
* Machine/profile metadata.

Errors should be actionable. They should explain what failed, why it matters, and what the user or agent should do next.

---

## 21. Configuration Requirements

modelctl should avoid hard-coded local assumptions.

Configuration should support:

* Router configuration file location.
* Model storage locations.
* Archive location.
* Registry location.
* Machine profile.
* Runtime profiles.
* Preferred active profiles.
* Fallback aliases.
* JSON output preferences where useful.

Configuration should be inspectable and validated by `doctor`.

Agents must not infer configuration by reading unrelated files when modelctl can provide it directly.

---

## 22. User Personas

### Manual User

Needs:

* Quick CLI inspection.
* Safe previews.
* Clear errors.
* Simple lifecycle operations.
* Confidence that fallback models remain available.
* A way to understand which models are worth keeping.

### Buster/Hermes Agent

Needs:

* Deterministic JSON.
* Status and suitability data.
* Safe model recommendations.
* Recovery paths.
* No requirement to infer local configuration manually.
* A reliable source of truth for model operations.

### OpenCode/Coding Agent

Needs:

* Reliable build-safe model selection.
* Tool-call reliability data.
* Context headroom guidance.
* Clear fallback options.
* Stable local model operations when cloud credits are unavailable.
* Model recommendations that avoid known corruption-prone configurations.

### Maintainer/Developer

Needs:

* Clear product requirements.
* Accurate implemented vs planned capability tracking.
* Testable safety rules.
* Maintainable command structure.
* Documentation before risky features.
* A roadmap that separates MVP, near-term, and future work.

---

## 23. Acceptance Criteria

A feature is not complete unless:

* The requirement is documented.
* Safety behaviour is clear.
* Read-only vs mutating behaviour is clear.
* JSON behaviour is defined where agents may use it.
* Tests exist for safety-critical paths.
* The implemented/planned command list is updated where relevant.
* The feature does not break fallback protection.
* The feature avoids local hard-coded assumptions.
* The feature gives actionable errors.

A mutating feature is not complete unless:

* Preview mode works.
* Apply/confirmation mode is explicit.
* Affected files/models/aliases are shown.
* Failure states are handled.
* Recovery guidance exists where practical.

An agent-facing feature is not complete unless:

* Output is deterministic.
* JSON is stable.
* Errors are machine-readable.
* Risk and warning states are clear.

---

## 24. Roadmap Notes

### Near-Term Priorities

* Preserve current safe CLI behaviour.
* Keep implemented vs planned status accurate.
* Add tests for new lifecycle operations.
* Improve requirements, safety, and roadmap documentation.
* Avoid agent-facing commands without tests and documentation.
* Add rollback tests if rollback remains part of the command surface.

### Medium-Term Priorities

* Add recommendation and classification capabilities.
* Add richer benchmark storage and comparison.
* Add active model hygiene workflows.
* Add router lifecycle management.
* Add learning log support.
* Add source metadata management.

### Long-Term Direction

modelctl becomes the deterministic local model operations layer used by agents.

Buster/Hermes remains the orchestration and natural-language layer.

OpenCode remains a coding client that consumes reliable modelctl outputs rather than guessing local model state.

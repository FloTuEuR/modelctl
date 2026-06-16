# Settings Rules and Recommendation Outcomes

`modelctl rules` explains the default decision rules used when evaluating model files, runtime settings, aliases, and router configuration.

These rules are deliberately simple, human-readable, and configurable. They are not meant to be perfect. They are meant to give modelctl a practical baseline for recommending good alias configurations for the current hardware and intended usage.

modelctl is designed for `llama.cpp` router mode, where aliases in a router `.ini` file point to GGUF model files and runtime settings.

The core idea is:

* Benchmark model files and runtime settings independently from aliases.
* Use benchmark and reliability evidence to recommend good alias configurations.
* Keep rules understandable enough for users, Hermes agents, OpenCode, and websites to inspect.
* Store rule configuration and results in modelctl-owned locations, not in the user’s home root folder.

---

## 1. Purpose of Rules

Rules help modelctl answer questions such as:

* Is this model fast enough for interactive use?
* Is this runtime configuration suitable for coding or tool use?
* Is this context size useful in practice?
* Does this model/settings combination fit the current hardware?
* Should this model be used for chat, coding, reasoning, long-context testing, or archive candidacy?
* Should modelctl recommend a new alias using these runtime settings?
* Should an existing alias be changed, kept, disabled, archived, or replaced?

Rules should be used by:

* `modelctl rules`
* `modelctl benchmark`
* `modelctl classify`
* `modelctl recommend`
* `modelctl add`
* `modelctl doctor`
* simple websites or dashboards
* Hermes agents and OpenCode workflows

---

## 2. Outcome Categories

modelctl should evaluate model/settings combinations across several outcome categories.

### Speed

Speed measures whether a model/settings combination is usable for the intended task.

Default baseline:

| Use case                 | Target                                                        |
| ------------------------ | ------------------------------------------------------------- |
| Interactive chat         | 20+ tokens/sec preferred                                      |
| Coding/tool use          | Stable output is more important than maximum speed            |
| Background/assistant use | Lower speed may be acceptable                                 |
| Long-context diagnostics | Speed may be secondary                                        |
| Large reasoning models   | Lower speed may be acceptable if quality is materially better |

Speed must not be the only success metric.

A fast model that produces corrupted JSON, broken tool calls, or poor reasoning should not be recommended for agentic workflows.

### Context

Context measures whether a runtime setting provides enough usable context for the intended task.

Default baseline:

| Outcome                         | Target                         |
| ------------------------------- | ------------------------------ |
| Basic chat                      | 8k+ context                    |
| Coding/tool use                 | 16k-32k reliable context       |
| General agent use               | 32k reliable context preferred |
| Long-context diagnostics        | 64k+ context useful            |
| Large document or repo analysis | 64k-128k useful when reliable  |

Configured context is not the same as reliable context.

modelctl should track practical reliability, including whether the model remains stable under tool calls, JSON output, and compaction pressure.

### Output Reliability

Output reliability measures whether the model/settings combination can complete practical tasks without drifting, corrupting output, or breaking structured responses.

Important signals:

* JSON validity.
* Tool-call stability.
* Repeated-token incidents.
* Garbage-character incidents.
* Patch/diff reliability.
* Instruction following.
* Compaction survivability.
* Behaviour near context limit.
* Behaviour under large prompts.
* Behaviour with limited output headroom.

For coding and agent workflows, reliability should outrank raw speed.

### Hardware Fit

Hardware fit measures whether the model/settings combination makes practical use of the current machine.

Consider:

* RAM usage.
* VRAM usage.
* GPU layer fit.
* CPU thread count.
* Backend support.
* KV cache size.
* Context size.
* Batch and ubatch settings.
* Parallelism.
* Power or thermal constraints where known.

Default preference:

* Prefer settings that are stable and practical on the current hardware.
* Prefer full or near-full GPU offload where it improves performance.
* Avoid settings that cause crashes, memory pressure, or unstable output.
* Do not assume the biggest possible context is the best setting.

### Quality

Quality measures whether output is good enough for the intended usage.

Quality should be judged by use case:

| Use case             | Quality requirement                                  |
| -------------------- | ---------------------------------------------------- |
| Fast chat            | Coherent, responsive, low latency                    |
| Coding/tool use      | Accurate, structured, instruction-following          |
| Reasoning/planning   | Careful, consistent, capable of multi-step reasoning |
| Summarisation        | Faithful, concise, low hallucination                 |
| Agent workflow       | Reliable, deterministic, JSON/tool-call safe         |
| Long-context testing | Stable over large prompts                            |

Quality must be considered alongside speed, context, and reliability.

### Storage Value

Storage value measures whether a model deserves to remain in active storage.

Signals:

* Is it used by active aliases?
* Is it better than another similar model?
* Does it have a unique use case?
* Is it reliable enough to justify active storage?
* Is it duplicated by a better model?
* Is it experimental or obsolete?
* Is it a good archive candidate?

Storage value supports archive recommendations.

Archive is not destructive. By default, archive moves a model out of active storage while preserving aliases.

### Delete Candidacy

Delete candidacy measures whether a model should be removed from managed storage.

Delete is destructive and requires explicit confirmation or an explicit apply flag.

Signals:

* Model is broken.
* Model is duplicated and no longer useful.
* Source is known and model can be redownloaded.
* No useful aliases depend on it.
* User explicitly wants it removed.
* Recovery metadata can be saved.

Delete recommendations must be more conservative than archive recommendations.

---

## 3. Default Rule Targets

These default targets provide a starting point.

| Rule                          | Default Target                                                    |
| ----------------------------- | ----------------------------------------------------------------- |
| Interactive speed             | 20+ tokens/sec preferred                                          |
| Basic useful context          | 8k+                                                               |
| Coding/tool-use context       | 16k-32k reliable                                                  |
| Good general agent context    | 32k reliable                                                      |
| Long-context useful threshold | 64k+ reliable                                                     |
| Ideal long-context threshold  | 128k reliable, only if stable                                     |
| Structured output             | Must produce valid JSON under expected workload                   |
| Tool use                      | Must avoid malformed tool calls and runaway output                |
| Coding use                    | Must produce stable patches, commands, and concise reasoning      |
| Archive candidate             | Redundant, weak, stale, unused, or experimental                   |
| Delete candidate              | Broken, unwanted, or safely redownloadable with recovery metadata |
| Home-folder hygiene           | No ad hoc files in the user’s home root folder                    |
| Delete confirmation           | Always required                                                   |

These targets should be configurable.

---

## 4. Use-Case Rules

### Fast Chat

Recommended properties:

* Fast response.
* Low memory pressure.
* Good conversational quality.
* Moderate context.
* Low setup overhead.

Typical preference:

* Smaller or efficient models.
* Conservative context.
* Stable generation settings.

### Coding and Tool Use

Recommended properties:

* Strong instruction following.
* Reliable JSON.
* Reliable tool-call behaviour.
* Stable patch/diff output.
* Enough context for files and diagnostics.
* Good behaviour under compaction.

Typical preference:

* Reliability over raw context size.
* Stable output over high creativity.
* Conservative output limits.
* Runtime settings proven by benchmark and reliability tests.

### Reasoning and Planning

Recommended properties:

* Good multi-step reasoning.
* Coherent long answers.
* Useful context window.
* Good factual discipline.
* Lower speed acceptable if output quality is better.

Typical preference:

* Stronger model over fastest model.
* Moderate to large reliable context.
* Settings that avoid drift.

### Long-Context Testing

Recommended properties:

* Large context.
* Stable behaviour under near-limit prompts.
* No repeated-token collapse.
* No JSON/tool-call corruption.

Typical preference:

* Treat as diagnostic unless reliability is proven.
* Do not recommend for routine coding only because configured context is large.

### Background Agent Tasks

Recommended properties:

* Low resource usage.
* Stable output.
* Good enough reasoning.
* Predictable latency.
* Suitable JSON output where required.

Typical preference:

* Efficient model.
* Reliable settings.
* Lower resource cost.

### Archive Candidate

Recommended properties:

* Not actively needed.
* Duplicated by better model.
* Poor benchmark or reliability outcome.
* Experimental or stale.
* Large active storage cost.

Archive should preserve aliases by default.

### Delete Candidate

Recommended properties:

* User explicitly wants it removed.
* Broken or unwanted.
* Recovery metadata can be created.
* Source metadata exists where possible.
* Relevant aliases/sections can be captured surgically.

Delete requires explicit confirmation or apply mode.

---

## 5. Benchmark Rules

Benchmarking is alias-independent.

A benchmark should evaluate:

* Model file.
* Runtime settings.
* Hardware capability.
* Backend behaviour.
* Context size.
* GPU layers.
* KV cache settings.
* Batch and ubatch.
* Threading.
* Prompt throughput.
* Generation throughput.
* Memory usage where available.
* Stability under practical workload.

Benchmark results should help modelctl recommend aliases.

Example flow:

```bash
modelctl benchmark /models/qwen.gguf --ctx-size 32768 --ngl 99
modelctl recommend --for coding --model /models/qwen.gguf
modelctl add /models/qwen.gguf --alias qwen-coding --from-recommendation
```

Benchmarking should not require an alias to exist first.

The alias should be the result of evidence-based configuration, not the prerequisite.

---

## 6. Recommendation Rules

Recommendations should combine:

* Current router `.ini` state.
* Model file metadata.
* Source metadata.
* Benchmark history.
* Reliability records.
* Hardware capability.
* Use-case rules.
* Active storage state.
* Archive state.
* User-defined preferences.

Recommendations should explain:

* Why this model or alias is recommended.
* Which evidence was used.
* Which assumptions were made.
* What risks remain.
* Which command should be run next.

Recommendations should be suitable for human-readable and JSON output.

Example recommendation types:

```bash
modelctl recommend --for chat
modelctl recommend --for coding
modelctl recommend --for reasoning
modelctl recommend --for agent
modelctl recommend --for archive
modelctl recommend --for delete
modelctl recommend --for alias-settings /path/to/model.gguf
```

---

## 7. Rules for Router ini Management

Because modelctl is built for `llama.cpp` router mode, rules must understand aliases and runtime settings in the router `.ini`.

Rules should help decide:

* Whether an alias name is clear.
* Whether multiple aliases point to the same model for different use cases.
* Whether an alias points to a missing file.
* Whether an alias has runtime settings that are too aggressive.
* Whether an alias is suitable for a website or agent.
* Whether a model file should be added to the `.ini`.
* Whether an alias should be disabled.
* Whether a model should be archived while aliases are preserved.

Rules must not assume that archive means alias removal.

Archive preserves aliases by default.

---

## 8. Rules for Monitoring

`monitor` is read-only.

Rules should help modelctl understand whether monitoring is configured.

Supported monitoring backends:

* systemd
* file
* docker/container
* modelctl-managed process
* configured read-only command
* none

`modelctl rules` should explain:

* Which backend is configured.
* Whether monitoring can follow logs.
* Whether recent logs can be shown.
* Which manual command is being abstracted where applicable.
* That monitor must not restart, reload, kill, or mutate anything.

---

## 9. Rules Configuration

Rules should eventually be configurable as data.

Example configuration shape:

```ini
[outcomes]
interactive_tokens_per_second = 20
context_basic = 8192
context_coding_min = 16384
context_coding_preferred = 32768
context_agent_preferred = 32768
context_long_useful = 65536
context_long_ideal = 131072
require_json_reliability_for_agent = true
require_tool_reliability_for_coding = true
prefer_stable_output_over_max_context = true
prefer_archive_over_delete = true
delete_requires_confirmation = true
archive_preserves_aliases_by_default = true
home_root_pollution_allowed = false

[benchmark]
store_results = true
alias_independent = true
compare_runtime_settings = true
feed_recommendations = true

[storage]
use_modelctl_owned_directories = true
store_recovery_manifests_under_modelctl = true
store_benchmarks_under_modelctl = true
store_logs_under_modelctl = true

[monitoring]
backend = auto
allow_follow = true
read_only = true
```

These values are examples, not hard-coded requirements.

---

## 10. Output Requirements for modelctl rules

`modelctl rules` should be useful to both humans and machines.

Human-readable output should show:

* Outcome targets.
* Use-case rules.
* Lifecycle rules.
* Benchmark rules.
* Monitoring rules.
* Storage rules.
* Confirmation rules.

JSON output should include:

* rule version
* configured thresholds
* use-case categories
* lifecycle behaviour
* benchmark behaviour
* monitoring behaviour
* storage locations where relevant
* confirmation requirements
* warnings where configuration is incomplete

`modelctl rules` should not mutate state.

---

## 11. Core Defaults

The default rules are:

* Archive preserves aliases by default.
* Restore is the opposite of archive.
* Delete requires explicit confirmation or apply mode.
* Recover uses delete recovery metadata and restores only relevant aliases/sections.
* Benchmarking is alias-independent.
* Recommendations should be evidence-based where evidence exists.
* Routine reversible operations do not require confirmation.
* modelctl artefacts must live in modelctl-owned locations.
* Monitor is read-only.
* Router `.ini` changes must preserve unrelated content.
* Agents and websites should query modelctl instead of guessing local state.

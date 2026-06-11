# Roadmap: model acquisition, freshness, benchmarking, and settings

These are important production features that are still incomplete in v0.1. Some command surfaces now do real work, while others remain planned. This document separates those states so users do not assume more automation exists than is currently implemented.

## 1. Hugging Face download

Planned command shape:

```bash
modelctl hf search qwen --max-params 14B
modelctl hf plan-download unsloth/Qwen3.6-35B-A3B-GGUF --quant UD-Q5_K_XL
modelctl hf download unsloth/Qwen3.6-35B-A3B-GGUF --quant UD-Q5_K_XL
```

Desired behavior:

- query Hugging Face model metadata and GGUF file trees;
- prefer repos with `llama.cpp`/GGUF support;
- download to a temporary file first;
- verify size/checksum metadata when available;
- atomically place the GGUF into the configured model directory;
- optionally add a disabled router alias for review.

## 2. up-to-date check

Current status: partially implemented.

Current command shape:

```bash
modelctl update-check
modelctl update-check alias:my-model
```

What works today:

- `modelctl update-check TARGET` can persist a freshness record when the model has known source metadata (`hf_repo` + `hf_file`) and remote metadata is available.
- `modelctl show TARGET` can display the cached Hugging Face freshness state.

Still planned:

- map local GGUF files back to a configured source repo/file when known;
- compare local metadata with Hugging Face revision, size, and etag/LFS metadata;
- report `current`, `newer remote available`, `local source unknown`, or `remote unavailable`;
- never replace a model without a reviewable plan.

## 3. Benchmark

Current status: partially implemented.

Current command shape:

```bash
modelctl benchmark alias:my-model
modelctl benchmark --all --prompt-set smoke
```

What works today:

- `modelctl benchmark TARGET` runs a real `llama-bench` invocation when available.
- prompt-processing and generation throughput are parsed and persisted.
- `modelctl show TARGET` can display the saved benchmark summary.

Still planned:

- run compact quality smoke prompts for instruction following and tool/chat-template sanity;
- record richer benchmark results in a human-readable benchmark file;
- compare candidates empirically instead of recommending from filename alone.

## 4. Suggest settings

This suggest settings feature is planned but not implemented in v0.1.

Planned command shape:

```bash
modelctl suggest-settings /path/to/model.gguf
modelctl suggest-settings --for-router
```

Desired behavior:

- inspect GGUF metadata where possible;
- identify context size, architecture, quant, and tokenizer/chat-template clues;
- suggest conservative router settings such as context, batch/ubatch, GPU layers, KV cache, and chat template flags;
- explain confidence and assumptions.

## 5. Hardware/config detection

This hardware/config detection feature is planned but not implemented in v0.1.

Planned command shape:

```bash
modelctl doctor --hardware
modelctl suggest-settings --detect-hardware
```

Desired behavior:

- detect OS, CPU cores, RAM, GPUs, VRAM, and available llama.cpp backend features;
- inspect the configured router binary/version;
- suggest safe initial settings for the user's actual environment;
- keep all recommendations as previews until the user applies them.

## Safety principle

All acquisition/update/benchmark/tuning features should follow the same modelctl pattern:

1. discover;
2. show a plan;
3. require explicit human approval for mutation;
4. write backups/metadata;
5. keep rollback or manual recovery instructions visible.

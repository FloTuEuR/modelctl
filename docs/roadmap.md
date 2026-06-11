# Roadmap: model acquisition, freshness, benchmarking, and settings

These are important production features, but they are **not implemented in v0.1**. They are documented here so users do not assume current commands already download, update, benchmark, or tune models automatically.

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

## 2. Up-to-date check

This up-to-date check feature is planned but not implemented in v0.1.

Planned command shape:

```bash
modelctl update-check
modelctl update-check alias:my-model
```

Desired behavior:

- map local GGUF files back to a configured source repo/file when known;
- compare local metadata with Hugging Face revision, size, and etag/LFS metadata;
- report `current`, `newer remote available`, `local source unknown`, or `remote unavailable`;
- never replace a model without a reviewable plan.

## 3. Benchmark

Planned command shape:

```bash
modelctl benchmark alias:my-model
modelctl benchmark --all --prompt-set smoke
```

Desired behavior:

- run local llama.cpp speed checks for prompt processing and generation throughput;
- run compact quality smoke prompts for instruction following and tool/chat-template sanity;
- record results in a human-readable benchmark file;
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

# Recommendation rules and outcomes

`modelctl rules` prints the default outcome targets used when judging whether a model/settings combination is good for a machine.

The rules are deliberately simple and human-readable so users can tune them later without changing code.

## Default outcomes

| Outcome | Target |
| --- | --- |
| Speed | 20+ tokens/sec for interactive use |
| Context | 65.5k context is good; 128k+ context is ideal |
| VRAM fit | Prefer settings where the whole model fits in VRAM |
| Quality | Output quality must be good for intended tasks, not just fast |
| Structured output | Model should handle large JSON without crashing or drifting |

## Current implementation status

- `modelctl show TARGET` displays placeholders and/or persisted values for minimum VRAM, average speed, estimated max context, estimated GPU layers, Hugging Face update state, and settings recommendation.
- `modelctl benchmark TARGET` runs a real `llama-bench` invocation when available and persists summary throughput for later display.
- `modelctl update-check TARGET` can persist a Hugging Face freshness record when source repo/file metadata is known.
- `modelctl add-entry --alias NAME --model PATH` shows a dry-run entry plan with estimated defaults. Applying entries is still planned.
- `modelctl enable` / `modelctl disable` apply real ini edits by default; `--dry-run` remains available for preview.

## Future config shape

A future config file can encode these rules as data, for example:

```ini
[outcomes]
interactive_tokens_per_second = 20
context_good = 65536
context_ideal = 131072
prefer_full_vram_fit = true
require_json_smoke_test = true
require_quality_smoke_test = true
```

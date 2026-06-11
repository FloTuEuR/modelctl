#!/usr/bin/env python3
"""modelctl prototype: portable, safe-by-default llama.cpp router ini manager.

This framework intentionally implements only read/import/list/dry-run planning.
It does not edit router ini files or delete model files yet.
"""
from __future__ import annotations

import argparse
import configparser
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modelctl_core import (
    apply_archive_plan,
    apply_delete_plan,
    augment_with_scanned_files,
    detect_from_ini,
    infer_archive_dirs,
    lab_model_paths,
    plan_archive_models,
    plan_delete_model,
)
import json


DEFAULT_CONFIG = Path.home() / ".config" / "modelctl" / "config.ini"


def _state_dir() -> Path:
    return Path(os.environ.get("MODELCTL_STATE_DIR", Path.home() / ".modelctl")).expanduser()


def _benchmark_dir(config: configparser.ConfigParser) -> Path:
    configured = config.get("state", "benchmark_dir", fallback=None)
    return Path(configured).expanduser() if configured else _state_dir() / "benchmarks"


def _benchmark_file(config: configparser.ConfigParser, model_path: str) -> Path:
    return _benchmark_dir(config) / f"{Path(model_path).name}.json"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


EXAMPLES = """
Examples:
  modelctl setup /path/to/models.ini                 # dry-run import preview
  modelctl setup                                      # launch setup wizard
  modelctl doctor                                    # check configured setup
  modelctl list                                      # show models and aliases
  modelctl show 1                                    # show model details
  modelctl aliases 1                                 # show aliases for a model
  modelctl delete 1 --dry-run                        # preview delete impact without changes
  modelctl delete 1                                  # interactive delete; removes aliases and file
  modelctl archive 1                                 # move file and disable aliases
  modelctl archive 1 --dry-run                       # preview archive impact
  modelctl archive --group lab                       # archive aliases under lab/testing section
"""

TARGET_HELP = """TARGET formats:
  N                       model row number from `modelctl list`, e.g. 1
  alias:NAME or NAME       router alias section, e.g. alias:my-model or my-model
  path:/models/file.gguf   explicit GGUF path
  file.gguf                GGUF filename shown in `modelctl list`
"""

SETUP_HELP = """Import an existing llama.cpp router models.ini/preset into modelctl's local config + registry.

Ways to run:
  modelctl setup                       # guided wizard; prompts for ini path and writes config/registry
  modelctl setup /path/to/models.ini   # direct path for non-interactive/scripted setup
  modelctl setup --ini /path/to/models.ini --registry /path/to/modelctl.yaml

Safety:
`setup` writes modelctl's own config/registry. It never edits your router ini.
"""

DELETE_HELP = f"""permanently deletes one GGUF file and removes router aliases that point at it.

{TARGET_HELP}
Safety:
  - `modelctl delete TARGET --dry-run` is safe for agents/scripts and makes no changes.
  - `modelctl delete TARGET` requires an interactive TTY and typed confirmation.
  - Non-interactive delete is blocked so agents cannot accidentally confirm deletion.

Examples:
  modelctl delete 1 --dry-run
  modelctl delete alias:my-model
  modelctl delete path:/models/model.gguf
"""

ARCHIVE_HELP = f"""Moves model files to the archive tree and disables affected aliases.

{TARGET_HELP}
Examples:
  modelctl archive 1                       # archive by model row number
  modelctl archive alias:my-model          # archive by alias
  modelctl archive 1 --dry-run             # preview without changing files
  modelctl archive --group lab             # archive aliases detected under lab/testing headings
"""

IMPORT_HELP = """Refresh modelctl's registry from the configured router ini.

Use this after manually editing your router preset or after moving/downloading models outside modelctl.
Router ini is not modified.

Examples:
  modelctl import
  modelctl --config /path/to/config.ini import
"""

DOCTOR_HELP = """Check configured paths and current capabilities.

Reports whether the configured router ini, registry, and model directories are readable/writable.
Also summarizes safety behavior, including that delete requires interactive typed confirmation.

Examples:
  modelctl doctor
  modelctl --config /path/to/config.ini doctor
"""

LIST_HELP = """List detected Models and Aliases from the configured router ini.

Models are numbered as simple IDs so you can pass `1` to show, aliases, delete, or archive.
STATUS summarizes whether a file is present/missing, active/archived, and enabled/disabled.
Aliases show the router section names pointing at each model.

Examples:
  modelctl list
  modelctl show 1
  modelctl aliases 1
"""

UPDATE_CHECK_HELP = """Check Hugging Face for a newer copy of a model file.

This command is intentionally metadata-driven: it needs a source repo/file recorded for the model before it can prove whether the local file is up to date.

Examples:
  modelctl update-check 1
  modelctl update-check alias:my-model
"""

ENABLE_HELP = """Enable a model alias in the router ini by uncommenting its section.

Applies by default. Use --dry-run to preview the ini edit first.

Examples:
  modelctl enable alias:my-model
  modelctl enable a2 --dry-run
"""

DISABLE_HELP = """Disable a model alias in the router ini by commenting its section.

Applies by default. Use --dry-run to preview the ini edit first.

Examples:
  modelctl disable alias:my-model
  modelctl disable a2 --dry-run
"""

ADD_ENTRY_HELP = """Create a new router ini entry with estimated best default flags/settings.

Applies by default. Use --dry-run to preview the generated entry first.

Examples:
  modelctl add-entry --alias my-model --model /path/to/model.gguf
  modelctl add-entry --alias my-model --model /path/to/model.gguf --dry-run
"""

BENCHMARK_HELP = """Benchmark a current model with llama.cpp and suggest settings.

Dry-run is not used here: the command tries to run a real benchmark immediately if `llama-bench` is available.
If `llama-bench` is missing, modelctl returns an actionable error that names the missing binary.

Examples:
  modelctl benchmark 1
  modelctl benchmark alias:my-model --prompt-set smoke
"""

RULES_HELP = """Show the outcome rules used to judge model/settings recommendations.

Default outcome targets include 20+ t/s, 65.5k context as good, 128k+ context as ideal, full VRAM fit, good output quality, and large JSON robustness.

Examples:
  modelctl rules
"""

SCAN_HELP = """Scan the configured models folder for GGUF files that exist on disk but are not yet in the router ini.

Applies by default. Use --dry-run to preview the discovered entries first.

Examples:
  modelctl scan
  modelctl scan --dry-run
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _format_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "missing"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(size_bytes)
    unit = units[0]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            break
        value /= 1024
    if unit == "B":
        return f"{int(value)} {unit}"
    return f"{value:.1f} {unit}"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    # Keep simple path strings unquoted for readability; quote only ambiguous YAML scalars.
    if text == "" or text.startswith(("{", "[", "#", "-", "!", "&", "*")) or ": " in text:
        return repr(text)
    return text


def write_registry_yaml(path: Path, imported: dict[str, Any]) -> None:
    """Write a tiny dependency-free YAML registry for imported state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "version: 1",
        f"imported_at: {_utc_now()}",
        f"router_ini: {imported['router_ini']}",
        f"download_dir: {_yaml_scalar(imported.get('download_dir'))}",
        "archive_dirs:",
    ]
    for archive_dir in imported.get("archive_dirs", []):
        lines.append(f"  - {_yaml_scalar(archive_dir)}")
    lines.append("aliases:")
    for alias in imported.get("aliases", []):
        lines.extend(
            [
                f"  - section: {_yaml_scalar(alias['section'])}",
                f"    enabled: {_yaml_scalar(alias['enabled'])}",
                f"    model_path: {_yaml_scalar(alias['model_path'])}",
            ]
        )
        params = alias.get("params") or {}
        if params:
            lines.append("    params:")
            for key in sorted(params):
                lines.append(f"      {key}: {_yaml_scalar(params[key])}")
    lines.append("models:")
    for model in imported.get("models", []):
        lines.extend(
            [
                f"  - path: {_yaml_scalar(model['path'])}",
                f"    state: {_yaml_scalar(model['state'])}",
                f"    size_bytes: {_yaml_scalar(model.get('size_bytes'))}",
                f"    location: {_yaml_scalar(model.get('location', 'active'))}",
                f"    action: {_yaml_scalar(model.get('action'))}",
                "    aliases:",
            ]
        )
        for alias_name in model.get("aliases", []):
            lines.append(f"      - {_yaml_scalar(alias_name)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_config(
    path: Path,
    router_ini: Path,
    registry: Path,
    download_dir: str | None,
    archive_dirs: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser()
    config["router"] = {"ini": str(router_ini)}
    config["state"] = {"registry": str(registry)}
    if download_dir:
        models_section = {"download_dir": download_dir}
        if archive_dirs:
            models_section["archive_dirs"] = ",".join(archive_dirs)
        config["models"] = models_section
    config["safety"] = {"confirm_delete": "true", "backup_ini": "true"}
    with path.open("w", encoding="utf-8") as fh:
        config.write(fh)


def load_config(path: Path) -> configparser.ConfigParser:
    if not path.exists():
        raise SystemExit(
            f"Config not found: {path}\n"
            f"Run: modelctl setup\n"
            f"Or give a direct path once: modelctl setup /path/to/models.ini --config {path}"
        )
    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    if not config.has_option("router", "ini"):
        raise SystemExit(f"Config missing [router] ini: {path}")
    return config


def _split_config_paths(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _import_from_config(config: configparser.ConfigParser) -> dict[str, Any]:
    imported = detect_from_ini(config.get("router", "ini"))
    download_dir = config.get("models", "download_dir", fallback=imported.get("download_dir"))
    model_dirs = [download_dir] if download_dir else []
    archive_dirs = _split_config_paths(config.get("models", "archive_dirs", fallback=""))
    if not archive_dirs:
        archive_dirs = infer_archive_dirs(download_dir)
    return augment_with_scanned_files(imported, model_dirs=model_dirs, archive_dirs=archive_dirs)


def _router_ini_from_setup_args(args: argparse.Namespace) -> Path | None:
    value = args.ini or args.ini_path
    return Path(value).expanduser().resolve() if value else None


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    print(f"{text}{suffix}: ", end="", flush=True)
    try:
        value = input().strip()
    except EOFError:
        return ""
    return value or (default or "")


def _yes_no_prompt(text: str, default: bool = True) -> bool:
    marker = "Y/n" if default else "y/N"
    answer = _prompt(f"{text} [{marker}]").lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def _find_setup_candidates() -> list[Path]:
    candidates = [
        Path.home() / "llama-models.ini",
        Path.home() / "models.ini",
        Path.home() / "llama.cpp" / "models.ini",
    ]
    return [p for p in candidates if p.exists()]


def _wizard_router_ini() -> Path | None:
    print("modelctl setup wizard")
    print("I need the path to your llama.cpp router models.ini / preset file.")
    candidates = _find_setup_candidates()
    default = str(candidates[0]) if candidates else None
    if candidates:
        print("Detected possible ini files:")
        for idx, path in enumerate(candidates, start=1):
            print(f"  {idx}. {path}")
    value = _prompt("Path to llama.cpp router models.ini", default)
    if value.isdigit() and candidates:
        idx = int(value) - 1
        if 0 <= idx < len(candidates):
            value = str(candidates[idx])
    return Path(value).expanduser().resolve() if value else None


def cmd_setup(args: argparse.Namespace) -> int:
    router_ini = _router_ini_from_setup_args(args)
    if router_ini is None:
        router_ini = _wizard_router_ini()
    if router_ini is None:
        print("setup needs a router ini path.", file=sys.stderr)
        print("Example: modelctl setup", file=sys.stderr)
        return 2
    if not router_ini.exists():
        print(f"router ini not found: {router_ini}", file=sys.stderr)
        print("Example: modelctl setup /path/to/models.ini", file=sys.stderr)
        return 2

    config_path = Path(args.config).expanduser().resolve()
    registry_path = Path(args.registry).expanduser().resolve() if args.registry else config_path.with_name("modelctl.yaml")

    imported = detect_from_ini(router_ini)
    archive_dirs = infer_archive_dirs(imported.get("download_dir"))
    model_dirs = [imported["download_dir"]] if imported.get("download_dir") else []
    imported = augment_with_scanned_files(imported, model_dirs=model_dirs, archive_dirs=archive_dirs)
    print("Detected/imported router ini:")
    print(f"  ini: {router_ini}")
    print(f"  aliases: {len(imported['aliases'])}")
    print(f"  models: {len(imported['models'])}")
    print(f"  download_dir: {imported.get('download_dir') or 'unknown'}")
    print(f"  archive_dirs: {', '.join(imported.get('archive_dirs', [])) or 'none detected'}")
    print(f"  config: {config_path}")
    print(f"  registry: {registry_path}")

    write_config(config_path, router_ini, registry_path, imported.get("download_dir"), imported.get("archive_dirs", []))
    write_registry_yaml(registry_path, imported)
    print("Setup written safely. Router ini was not modified.")
    print("Next:")
    print("  modelctl doctor")
    print("  modelctl list")
    return 0


def cmd_import(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    registry = Path(config.get("state", "registry", fallback=str(Path(args.config).with_name("modelctl.yaml")))).expanduser()
    imported = _import_from_config(config)
    write_registry_yaml(registry, imported)
    print(f"Imported {len(imported['aliases'])} aliases and {len(imported['models'])} models into {registry}")
    print("Router ini was not modified.")
    return 0


def _print_list(imported: dict[str, Any]) -> None:
    print("Models")
    print("ID  STATUS                         SIZE       ALIASES  PATH")
    for idx, model in enumerate(imported.get("models", []), start=1):
        location = str(model.get("location", "active"))
        file_state = str(model.get("state", "unknown"))
        enabled_aliases = sum(1 for alias in imported.get("aliases", []) if alias.get("model_path") == model["path"] and alias.get("enabled"))
        alias_state = "enabled" if enabled_aliases else "disabled" if model.get("aliases") else "unreferenced"
        status = f"{location}/{file_state}/{alias_state}"
        print(
            f"{idx:<3} {status:<30} {_format_size(model.get('size_bytes')):<10} "
            f"{len(model.get('aliases', [])):<7} {model['path']}"
        )
    print("")
    print("Aliases")
    print("ID   STATE     SECTION          MODEL")
    for idx, alias in enumerate(imported.get("aliases", []), start=1):
        state = "enabled" if alias.get("enabled") else "disabled"
        print(f"a{idx:<3} {state:<9} {alias['section']:<16} {alias['model_path']}")


def cmd_list(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    _print_list(imported)
    return 0


def _resolve_model_target(imported: dict[str, Any], target: str) -> str | None:
    if target.startswith("path:"):
        return target.split(":", 1)[1]
    if target.isdigit():
        idx = int(target) - 1
        models = imported.get("models", [])
        if 0 <= idx < len(models):
            return models[idx]["path"]
    if target.startswith("model:"):
        ref = target.split(":", 1)[1]
        if ref.isdigit():
            idx = int(ref) - 1
            models = imported.get("models", [])
            if 0 <= idx < len(models):
                return models[idx]["path"]
        for model in imported.get("models", []):
            if model["path"] == ref or Path(model["path"]).name == ref:
                return model["path"]
    # Fallback: direct path or filename match.
    for model in imported.get("models", []):
        if target == model["path"] or target == Path(model["path"]).name:
            return model["path"]
    return None


def _resolve_alias_target(imported: dict[str, Any], target: str) -> dict[str, Any] | None:
    ref = target.split(":", 1)[1] if target.startswith("alias:") else target
    if ref.startswith("a") and ref[1:].isdigit():
        idx = int(ref[1:]) - 1
        aliases = imported.get("aliases", [])
        if 0 <= idx < len(aliases):
            return aliases[idx]
    for alias in imported.get("aliases", []):
        if alias["section"] == ref or alias["section"].split(".")[-1] == ref:
            return alias
    return None


def _model_profile(model_path: str) -> dict[str, Any]:
    name = Path(model_path).name.lower()
    profiles = [
        (r"qwen.*0\.5b", {"family": "qwen", "params_b": 0.5, "layers": 24, "kv_bytes_per_token": 24576}),
        (r"qwen.*7b", {"family": "qwen", "params_b": 7.0, "layers": 28, "kv_bytes_per_token": 57344}),
        (r"qwen.*9b", {"family": "qwen", "params_b": 9.0, "layers": 36, "kv_bytes_per_token": 73728}),
        (r"qwen.*35b", {"family": "qwen", "params_b": 35.0, "layers": 64, "kv_bytes_per_token": 131072}),
        (r"gemma.*e2b|gemma.*2b", {"family": "gemma", "params_b": 2.0, "layers": 26, "kv_bytes_per_token": 26624}),
        (r"gemma.*e4b|gemma.*4b", {"family": "gemma", "params_b": 4.0, "layers": 34, "kv_bytes_per_token": 34816}),
        (r"gemma.*12b", {"family": "gemma", "params_b": 12.0, "layers": 42, "kv_bytes_per_token": 86016}),
        (r"gemma.*26b", {"family": "gemma", "params_b": 26.0, "layers": 52, "kv_bytes_per_token": 106496}),
    ]
    for pattern, profile in profiles:
        if re.search(pattern, name):
            return profile
    return {"family": "unknown", "params_b": None, "layers": None, "kv_bytes_per_token": None}


def _gpu_vram_bytes(args: argparse.Namespace) -> int | None:
    value = getattr(args, "gpu_vram_gib", None)
    if value is not None:
        return int(float(value) * (1024**3))
    env = os.environ.get("MODELCTL_GPU_VRAM_GIB")
    if env:
        try:
            return int(float(env) * (1024**3))
        except ValueError:
            return None
    return None


def _estimate_model_guidance(model: dict[str, Any] | None, gpu_vram_bytes: int | None = None, benchmark: dict[str, Any] | None = None, hf_status: dict[str, Any] | None = None) -> dict[str, str]:
    size = int(model.get("size_bytes") or 0) if model else 0
    path = model.get("path") if model else ""
    profile = _model_profile(path)
    if size:
        min_vram = int(size * 1.20)
        min_vram_text = f"{_format_size(min_vram)} (model bytes × 1.20 = {_format_size(size)} × 1.20 for weights + runtime overhead)"
    else:
        min_vram = 0
        min_vram_text = "unknown"

    free_for_kv = max((gpu_vram_bytes or 0) - min_vram, 0)
    kv_per_token = profile.get("kv_bytes_per_token") or 0
    if gpu_vram_bytes and kv_per_token:
        max_ctx = free_for_kv // kv_per_token
        max_ctx_text = (
            f"~{max_ctx:,} tokens (default KV cache f16, free VRAM {_format_size(free_for_kv)} ÷ {kv_per_token:,} B/token)"
            if max_ctx > 0 else
            f"0 tokens at default KV cache f16 (model already consumes the available {_format_size(gpu_vram_bytes)})"
        )
    else:
        max_ctx_text = "unknown; pass --gpu-vram-gib or set MODELCTL_GPU_VRAM_GIB to estimate default KV cache context"

    layers = profile.get("layers")
    if gpu_vram_bytes and size and layers:
        layer_budget = min_vram
        fitted_layers = max(0, min(layers, round(layers * min(gpu_vram_bytes, layer_budget) / layer_budget))) if layer_budget else 0
        pct = round((fitted_layers / layers) * 100) if layers else 0
        layer_text = f"{fitted_layers}/{layers} layers ({pct}% of layers) with context-first budgeting"
    else:
        layer_text = "unknown; need model profile and GPU VRAM to estimate layers"

    if benchmark and benchmark.get("generation_tokens_per_second") is not None:
        avg_speed = (
            f"generation {benchmark['generation_tokens_per_second']} tok/s; "
            f"prompt {benchmark.get('prompt_tokens_per_second', 'unknown')} tok/s"
        )
    else:
        avg_speed = "unknown; run `modelctl benchmark <id>` to record real t/s"
    hf_update = hf_status.get("status") if hf_status and hf_status.get("status") else "unknown; run `modelctl update-check <id>` after recording Hugging Face source metadata"
    if gpu_vram_bytes and size:
        if free_for_kv <= 0:
            settings = "suggest --cache-type-k q8_0 --cache-type-v q8_0 or reduce context/offload because default f16 KV cache has no headroom"
        elif kv_per_token and free_for_kv // kv_per_token < 65536:
            settings = "suggest --cache-type-k q8_0 --cache-type-v q8_0 to increase max context; keep context priority over extra GPU layers"
        else:
            settings = "suggest default KV cache f16 (--cache-type-k f16 --cache-type-v f16), flash-attn on, and --n-gpu-layers sized to keep the target context in VRAM"
    else:
        settings = "start conservative; provide GPU VRAM to compute context/layer recommendations"
    return {
        "minimum_vram": min_vram_text,
        "average_speed": avg_speed,
        "estimated_max_context": max_ctx_text,
        "estimated_gpu_layers": layer_text,
        "hf_update": hf_update,
        "settings": settings,
    }


def _print_model_details(imported: dict[str, Any], model_path: str, gpu_vram_bytes: int | None = None, benchmark: dict[str, Any] | None = None, hf_status: dict[str, Any] | None = None) -> None:
    model = next((m for m in imported.get("models", []) if m["path"] == model_path), None)
    print("Model")
    print(f"  path: {model_path}")
    if model:
        print(f"  state: {model['state']}")
        print(f"  location: {model.get('location', 'active')}")
        print(f"  status: {model.get('location', 'active')}/{model['state']}")
        print(f"  size: {_format_size(model.get('size_bytes'))}")
    aliases = [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]
    print(f"  aliases: {len(aliases)}")
    for alias in aliases:
        state = "enabled" if alias.get("enabled") else "disabled"
        print(f"    - {alias['section']} ({state})")
    guidance = _estimate_model_guidance(model, gpu_vram_bytes=gpu_vram_bytes, benchmark=benchmark, hf_status=hf_status)
    print("  capacity and freshness estimates:")
    print(f"    minimum vram: {guidance['minimum_vram']}")
    print(f"    average speed: {guidance['average_speed']}")
    print(f"    estimated max context: {guidance['estimated_max_context']}")
    print(f"    estimated gpu layers: {guidance['estimated_gpu_layers']}")
    print(f"    hugging face update: {guidance['hf_update']}")
    print(f"    settings recommendation: {guidance['settings']}")


def _hf_key_for_alias(alias: dict[str, Any]) -> str | None:
    repo = (alias.get("params") or {}).get("hf_repo")
    file = (alias.get("params") or {}).get("hf_file")
    if repo and file:
        return f"{repo}::{file}"
    return None


def cmd_show(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    model_path = _resolve_model_target(imported, args.target)
    if model_path:
        aliases = [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]
        key = _hf_key_for_alias(aliases[0]) if aliases else None
        hf_state = _load_json(_state_dir() / 'hf-status.json') or {}
        _print_model_details(imported, model_path, gpu_vram_bytes=_gpu_vram_bytes(args), benchmark=_load_json(_benchmark_file(config, model_path)), hf_status=hf_state.get(key) if key else None)
        return 0
    alias = _resolve_alias_target(imported, args.target)
    if alias:
        state = "enabled" if alias.get("enabled") else "disabled"
        print("Alias")
        print(f"  section: {alias['section']}")
        print(f"  state: {state}")
        print(f"  model: {alias['model_path']}")
        print("  params:")
        for key, value in sorted(alias.get("params", {}).items()):
            print(f"    {key}: {value}")
        return 0
    print(f"Could not resolve target: {args.target}", file=sys.stderr)
    print("Try: modelctl list", file=sys.stderr)
    return 2


def cmd_aliases(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    model_path = _resolve_model_target(imported, args.target)
    if model_path is None:
        print(f"Could not resolve model target: {args.target}", file=sys.stderr)
        print("Try: modelctl list", file=sys.stderr)
        return 2
    aliases = [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]
    print(f"Aliases for {model_path}")
    for alias in aliases:
        state = "enabled" if alias.get("enabled") else "disabled"
        print(f"  - {alias['section']} ({state})")
    return 0


def cmd_doctor(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    router_ini = Path(config.get("router", "ini")).expanduser()
    registry = Path(config.get("state", "registry", fallback=str(Path(args.config).with_name("modelctl.yaml")))).expanduser()
    exit_code = 0
    if router_ini.exists() and router_ini.is_file():
        print(f"OK router ini readable: {router_ini}")
        imported = _import_from_config(config)
        print(f"OK aliases detected: {len(imported['aliases'])}")
        print(f"OK models detected: {len(imported['models'])}")
        archived_count = sum(1 for model in imported.get("models", []) if model.get("location") == "archived")
        if archived_count:
            print(f"OK archived models detected: {archived_count}")
    else:
        print(f"ERROR router ini missing: {router_ini}")
        imported = {"aliases": [], "models": []}
        exit_code = 1

    try:
        registry.parent.mkdir(parents=True, exist_ok=True)
        probe = registry.parent / ".modelctl-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print(f"OK registry writable: {registry}")
    except OSError as exc:
        print(f"ERROR registry not writable: {registry} ({exc})")
        exit_code = 1

    download_dir = config.get("models", "download_dir", fallback=None) or imported.get("download_dir")
    if download_dir:
        p = Path(download_dir).expanduser()
        if p.exists() and p.is_dir():
            print(f"OK download dir exists: {p}")
        else:
            print(f"WARN download dir missing: {p}")
    else:
        print("WARN download dir unknown")
    print("Safety: delete requires interactive typed confirmation unless --dry-run; archive/apply commands accept --dry-run previews when you want smoke-test behavior.")
    return exit_code


def _print_delete_plan(plan: dict[str, Any], dry_run: bool) -> None:
    print("DRY RUN: delete model impact preview" if dry_run else "DELETE: model removal requires confirmation")
    print(f"  model: {plan['model_path']}")
    print(f"  aliases to remove from router ini: {len(plan['aliases_impacted'])}")
    for alias in plan["aliases_impacted"]:
        print(f"    - {alias}")
    print(f"  files to permanently delete: {len(plan['files_to_delete'])}")
    for path in plan["files_to_delete"]:
        print(f"    - {path}")
    for warning in plan["warnings"]:
        print(f"  warning: {warning}")


def _confirm_delete_interactively(plan: dict[str, Any]) -> bool:
    if not sys.stdin.isatty():
        print("Refusing delete: interactive TTY is required for destructive delete confirmation.", file=sys.stderr)
        print("Agents and scripts should use --dry-run. Run from a real terminal to delete.", file=sys.stderr)
        return False
    phrase = f"delete {Path(plan['model_path']).name}"
    print("")
    print("This will permanently delete the model file and remove the aliases listed above.")
    print(f"Type exactly: {phrase}")
    answer = input("> ").strip()
    return answer == phrase


def cmd_delete(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    model_path = _resolve_model_target(imported, args.target)
    if model_path is None:
        alias = _resolve_alias_target(imported, args.target)
        model_path = alias.get("model_path") if alias else None
    if model_path is None:
        print(f"Could not resolve model target: {args.target}", file=sys.stderr)
        print("Try: modelctl list", file=sys.stderr)
        return 2
    plan = plan_delete_model(imported, model_path)
    if args.dry_run:
        _print_delete_plan(plan, dry_run=True)
        print("No files or ini entries were changed.")
        return 0
    _print_delete_plan(plan, dry_run=False)
    if not _confirm_delete_interactively(plan):
        print("Delete cancelled. No files or ini entries were changed.")
        return 1
    try:
        result = apply_delete_plan(plan)
    except Exception as exc:
        print(f"delete failed safely: {exc}", file=sys.stderr)
        return 1
    print(f"APPLIED: deleted {len(result['deleted_files'])} file(s) and removed {len(plan['aliases_impacted'])} alias section(s)")
    print(f"  router ini backup: {result['router_ini_backup']}")
    return 0


def _default_plan_path(config_path: str, prefix: str = "archive") -> Path:
    stamp = _utc_now().replace(":", "").replace("-", "")
    return Path(config_path).expanduser().with_name("plans") / f"{prefix}-{stamp}.json"


def _print_archive_plan(plan: dict[str, Any], dry_run: bool) -> None:
    print("DRY RUN: archive model impact preview" if dry_run else "APPLIED: archive model")
    print(f"  aliases policy: {plan['aliases_policy']}")
    print(f"  router ini: {plan['router_ini']}")
    print(f"  models impacted: {len(plan['entries'])}")
    for idx, entry in enumerate(plan.get("entries", []), start=1):
        print(f"  model {idx}:")
        print(f"    source: {entry['source']}")
        print(f"    archive destination: {entry['destination']}")
        print(f"    aliases impacted: {len(entry['aliases_impacted'])}")
        for alias in entry["aliases_impacted"]:
            print(f"      - {alias}")
    for warning in plan.get("warnings", []):
        print(f"  warning: {warning}")


def _archive_targets(args: argparse.Namespace, imported: dict[str, Any]) -> list[str] | None:
    if args.group:
        if args.group.lower() != "lab":
            print(f"Unsupported archive group: {args.group}", file=sys.stderr)
            print("Currently supported: --group lab", file=sys.stderr)
            return None
        targets = lab_model_paths(imported)
        if not targets:
            print("No lab/testing aliases were found in the router ini.", file=sys.stderr)
            return None
        return targets
    if not args.target:
        print("archive needs at least one model target or --group lab", file=sys.stderr)
        return None
    targets: list[str] = []
    for target in args.target:
        model_path = _resolve_model_target(imported, target)
        if model_path is None:
            alias = _resolve_alias_target(imported, target)
            model_path = alias.get("model_path") if alias else None
        if model_path is None:
            print(f"Could not resolve model or alias target: {target}", file=sys.stderr)
            print("Try: modelctl list", file=sys.stderr)
            return None
        targets.append(model_path)
    return targets


def cmd_archive(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    targets = _archive_targets(args, imported)
    if targets is None:
        return 2
    plan = plan_archive_models(imported, targets)
    if getattr(args, 'dry_run', False):
        _print_archive_plan(plan, dry_run=True)
        print("No files or ini entries were changed. Re-run without --dry-run to apply this exact archive plan.")
        return 0
    plan_path = Path(args.plan).expanduser() if args.plan else _default_plan_path(args.config)
    try:
        applied = apply_archive_plan(plan, plan_path=plan_path)
    except Exception as exc:
        print(f"archive failed safely: {exc}", file=sys.stderr)
        return 1
    _print_archive_plan(applied, dry_run=False)
    print("Archive applied. Router ini backup and recovery metadata were written.")
    return 0


def _find_llama_bench() -> str | None:
    env = os.environ.get('MODELCTL_LLAMA_BENCH')
    if env and Path(env).exists():
        return env
    candidates = [
        shutil.which("llama-bench"),
        str(Path.home() / "llama.cpp" / "build" / "bin" / "llama-bench"),
        str(Path.home() / "llama.cpp" / "build" / "tools" / "llama-bench"),
        str(Path.home() / "llama.cpp" / "tools" / "llama-bench"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _slugify_alias(path: str) -> str:
    stem = Path(path).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return stem or "model"


def _scan_unmanaged_models(imported: dict[str, Any], download_dir: str | None) -> list[dict[str, str]]:
    if not download_dir:
        return []
    root = Path(download_dir).expanduser()
    if not root.exists() or not root.is_dir():
        return []
    known = {a["model_path"] for a in imported.get("aliases", [])}
    found = []
    for path in sorted(root.glob("*.gguf")):
        if str(path) in known:
            continue
        found.append({"path": str(path), "alias": _slugify_alias(str(path))})
    return found


def _append_disabled_entries(router_ini: Path, entries: list[dict[str, str]]) -> None:
    existing = router_ini.read_text(encoding="utf-8") if router_ini.exists() else ""
    chunks = [existing.rstrip(), ""] if existing.strip() else []
    for entry in entries:
        chunks.extend([
            f"# [{entry['alias']}]",
            f"# model = {entry['path']}",
            "# ctx-size = 65536",
            "# n-gpu-layers = 999",
            "# flash-attn = on",
            "",
        ])
    router_ini.write_text("\n".join(chunks).rstrip() + "\n", encoding="utf-8")


def cmd_update_check(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    alias = _resolve_alias_target(imported, args.target)
    if not alias:
        model_path = _resolve_model_target(imported, args.target)
        alias = next((a for a in imported.get('aliases', []) if a.get('model_path') == model_path), None)
    if not alias:
        print(f"Could not resolve target for update-check: {args.target}", file=sys.stderr)
        return 2
    repo = (alias.get('params') or {}).get('hf_repo')
    file = (alias.get('params') or {}).get('hf_file')
    if not repo or not file:
        print('Hugging Face update check')
        print('status: source metadata not recorded yet')
        print('next: record repo/file metadata for this model, then compare remote revision/etag/size')
        return 0
    if os.environ.get('MODELCTL_HF_TREE_JSON'):
        tree = json.loads(os.environ['MODELCTL_HF_TREE_JSON'])
    else:
        print('Hugging Face update check requires hf metadata access; set MODELCTL_HF_TREE_JSON for tests or install hf/web fetch support.', file=sys.stderr)
        return 1
    remote = next((x for x in tree if x.get('path') == file and x.get('type') == 'file'), None)
    local_size = Path(alias['model_path']).stat().st_size if Path(alias['model_path']).exists() else None
    status = 'up-to-date' if remote and local_size == remote.get('size') else 'update-available'
    key = f"{repo}::{file}"
    store = _load_json(_state_dir() / 'hf-status.json') or {}
    store[key] = {'status': status, 'remote_size': remote.get('size') if remote else None, 'local_size': local_size}
    _save_json(_state_dir() / 'hf-status.json', store)
    print('Hugging Face update check')
    print(f'  repo: {repo}')
    print(f'  file: {file}')
    print(f'  status: {status}')
    return 0


def _rewrite_alias_block(router_ini: Path, section: str, enable: bool) -> bool:
    text = router_ini.read_text(encoding='utf-8')
    lines = text.splitlines()
    changed = False
    in_section = False
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        normalized = stripped[2:] if stripped.startswith('# ') else stripped[1:] if stripped.startswith('#') else stripped
        if normalized == f'[{section}]':
            in_section = True
            desired = f'[{section}]' if enable else f'# [{section}]'
            if lines[i] != desired:
                lines[i] = desired
                changed = True
            continue
        if in_section and normalized.startswith('[') and normalized.endswith(']'):
            in_section = False
        if in_section:
            desired = normalized if enable else (normalized if normalized.startswith('#') else f'# {normalized}')
            if enable:
                desired = normalized
            else:
                desired = normalized if normalized.startswith('#') else f'# {normalized}'
            if lines[i] != desired:
                lines[i] = desired
                changed = True
    if changed:
        router_ini.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return changed


def cmd_enable_disable(args: argparse.Namespace, config: configparser.ConfigParser, enable: bool) -> int:
    imported = _import_from_config(config)
    alias = _resolve_alias_target(imported, args.target)
    if not alias:
        print(f"Could not resolve alias target: {args.target}", file=sys.stderr)
        print("Try: modelctl list", file=sys.stderr)
        return 2
    action = "enable" if enable else "disable"
    if getattr(args, 'dry_run', False):
        print(f"DRY RUN: would {action} alias [{alias['section']}] in router ini")
        print(f"  model: {alias['model_path']}")
        print("No ini entries were changed.")
        return 0
    router_ini = Path(config.get('router', 'ini')).expanduser()
    changed = _rewrite_alias_block(router_ini, alias['section'], enable=enable)
    print(f"APPLIED: {action}d alias [{alias['section']}] in {router_ini}" + ("" if changed else " (already in requested state)"))
    return 0


def cmd_add_entry(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    print("Router ini entry plan with estimated best defaults")
    print(f"  alias: {args.alias}")
    print(f"  model: {args.model}")
    print("  estimated flags: ctx-size = 65536, n-gpu-layers = 999, flash-attn = true")
    if getattr(args, 'dry_run', False):
        print("No ini entries were changed.")
        return 0
    router_ini = Path(config.get("router", "ini")).expanduser()
    existing = router_ini.read_text(encoding="utf-8") if router_ini.exists() else ""
    block = "\n".join([
        f"[{args.alias}]",
        f"model = {args.model}",
        "ctx-size = 65536",
        "n-gpu-layers = 999",
        "flash-attn = on",
        "",
    ])
    router_ini.write_text((existing.rstrip() + "\n\n" if existing.strip() else "") + block, encoding="utf-8")
    print(f"APPLIED: appended [{args.alias}] to {router_ini}")
    return 0


def cmd_benchmark(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    model_path = _resolve_model_target(imported, args.target)
    if model_path is None:
        alias = _resolve_alias_target(imported, args.target)
        model_path = alias.get("model_path") if alias else None
    if model_path is None:
        print(f"Could not resolve model target: {args.target}", file=sys.stderr)
        print("Try: modelctl list", file=sys.stderr)
        return 2
    bench = _find_llama_bench()
    if not bench:
        print("llama-bench not found. Install llama.cpp or add llama-bench to PATH.", file=sys.stderr)
        return 1
    if str(bench).endswith('.py'):
        cmd = [sys.executable, bench]
    else:
        cmd = [bench, "-m", model_path, "-o", "json", "-r", "1", "-p", "256", "-n", "64"]
    try:
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except OSError as exc:
        print(f"Failed to execute llama-bench: {exc}", file=sys.stderr)
        return 1
    combined = (result.stderr + "\n" + result.stdout).strip()
    print("llama.cpp benchmark")
    print(f"  target: {model_path}")
    print(f"  command: {' '.join(cmd)}")
    print(combined)
    if result.returncode != 0:
        return result.returncode
    try:
        payload = json.loads(result.stdout)
        prompt = next((x.get('avg_ts') for x in payload if x.get('n_prompt', 0) > 0), None)
        gen = next((x.get('avg_ts') for x in payload if x.get('n_gen', 0) > 0), None)
        summary = {'model_path': model_path, 'prompt_tokens_per_second': prompt, 'generation_tokens_per_second': gen, 'captured_at': _utc_now()}
        _save_json(_benchmark_file(config, model_path), summary)
        print(f"prompt_tokens_per_second: {prompt} tok/s")
        print(f"generation_tokens_per_second: {gen} tok/s")
    except Exception:
        pass
    return 0


def cmd_scan(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    download_dir = config.get("models", "download_dir", fallback=None) or imported.get("download_dir")
    found = _scan_unmanaged_models(imported, download_dir)
    print("Scan for unmanaged GGUF files")
    print(f"  download dir: {download_dir or 'unknown'}")
    print(f"  unmanaged models found: {len(found)}")
    for entry in found:
        print(f"    - {entry['path']} -> [{entry['alias']}] (disabled entry preview)")
    if getattr(args, 'dry_run', False):
        print("No ini entries were changed. Re-run without --dry-run to append disabled ini entries for the models above.")
        return 0
    if not found:
        print("Nothing to add.")
        return 0
    router_ini = Path(config.get("router", "ini")).expanduser()
    _append_disabled_entries(router_ini, found)
    print(f"APPLIED: appended {len(found)} disabled entry/entries to {router_ini}")
    return 0


def cmd_rules(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    print("Outcome rules for model/settings recommendations")
    print("  speed: 20+ t/s target")
    print("  context: 65.5k good, 128k+ ideal")
    print("  memory: whole model fits in VRAM when possible")
    print("  quality: output quality is good for intended tasks")
    print("  robustness: handles large JSON without crashing")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Portable safe-by-default llama.cpp router ini model manager",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to modelctl config.ini")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser(
        "setup",
        help="Import existing router ini and write minimal modelctl config/registry",
        description="Import a llama.cpp router models.ini/preset into modelctl's local registry.",
        epilog=SETUP_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    setup.add_argument("ini_path", nargs="?", metavar="/path/to/models.ini", help="Path to llama.cpp router models ini/preset")
    setup.add_argument("--ini", required=False, metavar="/path/to/models.ini", help="Path to llama.cpp router models ini/preset")
    setup.add_argument("--config", default=str(DEFAULT_CONFIG), metavar="CONFIG.ini", help="Path to write config.ini")
    setup.add_argument("--registry", metavar="modelctl.yaml", help="Path to write modelctl.yaml registry")

    sub.add_parser(
        "import",
        help="Refresh registry from configured router ini without router changes",
        description="Refresh modelctl's registry from the configured router ini without changing the router ini.",
        epilog=IMPORT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub.add_parser(
        "doctor",
        help="Check configured paths and current capabilities",
        description="Check configured paths, writable state, and safety capabilities.",
        epilog=DOCTOR_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub.add_parser(
        "list",
        help="List detected models and aliases from configured router ini",
        description="List detected Models and Aliases from the configured router ini.",
        epilog=LIST_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show = sub.add_parser(
        "show",
        help="Show details for a model or alias target",
        description="Show details for one model or alias target.",
        epilog=TARGET_HELP + "\nExamples:\n  modelctl show 1\n  modelctl show alias:my-model\n  modelctl show path:/models/model.gguf\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show.add_argument("target", metavar="TARGET", help="Model or alias target; see formats below")
    show.add_argument("--gpu-vram-gib", type=float, help="Optional GPU VRAM size in GiB to estimate context and layer fit")
    aliases = sub.add_parser(
        "aliases",
        help="List aliases for a model target",
        description="List router aliases that point at a model target.",
        epilog=TARGET_HELP + "\nExamples:\n  modelctl aliases 1\n  modelctl aliases alias:my-model\n  modelctl aliases filename.gguf\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    aliases.add_argument("target", metavar="TARGET", help="Model target; e.g. 1, path:/models/model.gguf, or filename.gguf")
    delete = sub.add_parser(
        "delete",
        help="Interactively delete a model file and remove aliases; --dry-run to preview",
        description="Permanently deletes a model file and removes router aliases after interactive confirmation.",
        epilog=DELETE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    delete.add_argument("target", metavar="TARGET", help="Model target; e.g. 1, alias:my-model, path:/models/model.gguf, or filename.gguf")
    delete.add_argument("--dry-run", action="store_true", help="Preview file and alias removals without changing anything")
    archive = sub.add_parser(
        "archive",
        help="Archive model files and disable aliases",
        description="Move model files to the archive tree and disable affected aliases.",
        epilog=ARCHIVE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    archive.add_argument("target", nargs="*", metavar="TARGET", help="One or more model targets; e.g. 1 alias:my-model path:/models/model.gguf")
    archive.add_argument("--group", metavar="NAME", help="Archive a named group; currently supports: lab")
    archive.add_argument("--dry-run", action="store_true", help="Preview the archive plan without changing anything")
    archive.add_argument("--plan", metavar="PLAN.json", help="Optional path to write recovery metadata JSON")
    update_check = sub.add_parser(
        "update-check",
        help="Check Hugging Face metadata for model updates",
        description="Check Hugging Face for a newer copy of a model file.",
        epilog=UPDATE_CHECK_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    update_check.add_argument("target", nargs="?", metavar="TARGET", help="Optional model target, e.g. 1 or alias:my-model")
    enable = sub.add_parser("enable", help="Enable an alias in the router ini", description="Enable a disabled alias in the router ini.", epilog=ENABLE_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    enable.add_argument("target", metavar="ALIAS", help="Alias target, e.g. a2 or alias:my-model")
    enable.add_argument("--dry-run", action="store_true", help="Preview ini edit without changing anything")
    disable = sub.add_parser("disable", help="Disable an alias in the router ini", description="Disable an alias in the router ini.", epilog=DISABLE_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    disable.add_argument("target", metavar="ALIAS", help="Alias target, e.g. a2 or alias:my-model")
    disable.add_argument("--dry-run", action="store_true", help="Preview ini edit without changing anything")
    add_entry = sub.add_parser("add-entry", help="Create an ini entry with estimated best defaults", description="Create a router ini entry with estimated best default flags/settings.", epilog=ADD_ENTRY_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_entry.add_argument("--alias", required=True, help="Router alias/section name to create")
    add_entry.add_argument("--model", required=True, help="GGUF model path for the new entry")
    add_entry.add_argument("--dry-run", action="store_true", help="Preview entry without appending anything")
    benchmark = sub.add_parser("benchmark", help="Benchmark a model with llama.cpp and suggest settings", description="Benchmark a current model with llama.cpp and suggest the most appropriate settings.", epilog=BENCHMARK_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    benchmark.add_argument("target", metavar="TARGET", help="Model target, e.g. 1 or alias:my-model")
    benchmark.add_argument("--prompt-set", default="smoke", help="Prompt set to run; default: smoke")
    scan = sub.add_parser("scan", help="Scan for manually added GGUFs not yet in the ini", description="Scan the models folder for GGUF files not yet referenced by the router ini.", epilog=SCAN_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    scan.add_argument("--dry-run", action="store_true", help="Preview discovered entries without appending anything")
    sub.add_parser("rules", help="Show model outcome rules", description="Show the outcomes used to judge model/settings recommendations.", epilog=RULES_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "setup":
        return cmd_setup(args)

    config = load_config(Path(args.config).expanduser())
    if args.command == "import":
        return cmd_import(args, config)
    if args.command == "doctor":
        return cmd_doctor(args, config)
    if args.command == "list":
        return cmd_list(args, config)
    if args.command == "show":
        return cmd_show(args, config)
    if args.command == "aliases":
        return cmd_aliases(args, config)
    if args.command == "delete":
        return cmd_delete(args, config)
    if args.command == "archive":
        return cmd_archive(args, config)
    if args.command == "update-check":
        return cmd_update_check(args, config)
    if args.command == "enable":
        return cmd_enable_disable(args, config, True)
    if args.command == "disable":
        return cmd_enable_disable(args, config, False)
    if args.command == "add-entry":
        return cmd_add_entry(args, config)
    if args.command == "benchmark":
        return cmd_benchmark(args, config)
    if args.command == "scan":
        return cmd_scan(args, config)
    if args.command == "rules":
        return cmd_rules(args, config)
    parser.error(f"Unhandled command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

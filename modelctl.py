#!/usr/bin/env python3
"""modelctl prototype: portable, safe-by-default llama.cpp router ini manager.

This framework intentionally implements only read/import/list/dry-run planning.
It does not edit router ini files or delete model files yet.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from pathlib import Path
from typing import Any

from modelctl_core import (
    apply_archive_plan,
    apply_delete_plan,
    apply_restore_plan,
    apply_recover_manifest,
    augment_with_scanned_files,
    detect_from_ini,
    infer_archive_dirs,
    lab_model_paths,
    plan_archive_models,
    plan_delete_model,
)



DEFAULT_CONFIG = Path.home() / ".config" / "modelctl" / "config.ini"


def _xdg_dir(env_name: str, default_relative: str) -> Path:
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured).expanduser()
    return Path.home().joinpath(*default_relative.split("/")).expanduser()


def _config_dir() -> Path:
    return _xdg_dir("MODELCTL_CONFIG_DIR", ".config/modelctl")


def _data_dir() -> Path:
    return _xdg_dir("MODELCTL_DATA_DIR", ".local/share/modelctl")


def _state_dir() -> Path:
    return _xdg_dir("MODELCTL_STATE_DIR", ".local/state/modelctl")


def _cache_dir() -> Path:
    return _xdg_dir("MODELCTL_CACHE_DIR", ".cache/modelctl")


def _recovery_dir(config: configparser.ConfigParser | None = None) -> Path:
    configured = config.get("state", "recovery_dir", fallback=None) if config is not None else None
    return Path(configured).expanduser() if configured else _state_dir() / "recovery"


def _benchmark_dir(config: configparser.ConfigParser) -> Path:
    configured = config.get("state", "benchmark_dir", fallback=None)
    return Path(configured).expanduser() if configured else _data_dir() / "benchmarks"


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


def _json_envelope(
    command: str,
    data: dict[str, Any] | None = None,
    *,
    status: str = "ok",
    warnings: list[str] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "command": command,
        "data": data or {},
        "warnings": warnings or [],
        "error": error,
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


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
  modelctl archive 1                                 # move file and preserve aliases
  modelctl archive 1 --disable-aliases               # move file and disable directly linked aliases
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

ARCHIVE_HELP = f"""Moves model files to the archive tree while preserving aliases by default.

{TARGET_HELP}Examples:
  modelctl archive 1                       # archive by model row number; preserve aliases
  modelctl archive alias:my-model          # archive by alias; preserve aliases
  modelctl archive 1 --disable-aliases     # also disable aliases directly linked to the model
  modelctl archive 1 --dry-run             # preview without changing files
  modelctl archive --group lab             # archive aliases detected under lab/testing headings

Archive writes movement/recovery metadata for restore in modelctl-owned plan storage.
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

ADD_HELP = """Create a new router ini entry with estimated best default flags/settings.

Applies by default. Use --dry-run to preview the generated entry first.

Examples:
  modelctl add --alias my-model --model /path/to/model.gguf
  modelctl add --alias my-model --model /path/to/model.gguf --dry-run
"""

ADD_ENTRY_HELP = """deprecated compatibility alias for `modelctl add`.

Use `modelctl add` for new scripts and documentation. This temporary alias keeps
older automation working while the command surface transitions.

Examples:
  modelctl add --alias my-model --model /path/to/model.gguf
  modelctl add-entry --alias my-model --model /path/to/model.gguf
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

RESTORE_HELP = f"""Move archived model files back to active storage.

{TARGET_HELP}This is the opposite of archive: it restores archived GGUF files to active storage
and preserves unrelated router ini content. Implementation is staged after command
surface alignment.
"""

RECOVER_HELP = """Recover aliases from a delete recovery manifest.

Uses focused recovery manifest data to recreate only affected aliases/sections
after the model file exists again, preserving unrelated router ini changes.
Implementation is staged after delete manifest alignment.
"""

MONITOR_HELP = """Check read-only local llama server status or recent logs without changing anything.

ports identify local llama servers. Use `discover` to find them first, then use a
port such as `8080` or `8082` for a specific server.

Usage:
  modelctl monitor
  modelctl monitor discover
  modelctl monitor 8080
  modelctl monitor 8082

Examples:
  modelctl monitor
    Discover local llama servers and suggest next commands.

  modelctl monitor 8080
    Show status for the llama server on port 8080.

  modelctl monitor 8082
    Show status for the mini/helper llama server on port 8082.

  modelctl tail 8080
    Follow logs for the service explicitly mapped to port 8080.

  modelctl restart 8080
    Restart examples are shown for operator context only; monitor commands never restart services.

Options:
  --json
    Print machine-readable output.

  --lines N
    Show N recent log lines when logs are available.

  --follow
    Follow logs when supported.
"""


TAIL_HELP = """Examples:
  modelctl tail 8080
    Follow logs for the service configured under [monitor.ports] 8080 = llama-cuda.service.

Config example:
  [monitor.ports]
  8080 = llama-cuda.service

This command is read-only and delegates to the configured systemd service log. It does not scan ports, guess services, or restart anything.
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
    router_ini = Path(config.get("router", "ini")).expanduser()
    if not router_ini.exists():
        raise SystemExit(
            f"router ini not found: {router_ini}\n"
            "Run: modelctl setup /path/to/models.ini\n"
            "Or import a valid router ini after fixing the configured path."
        )
    imported = detect_from_ini(router_ini)
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



def _print_models_only(models: list[dict[str, Any]]) -> None:
    print("Models")
    print("ID  STATUS                         SIZE       ALIASES  PATH")
    for idx, model in enumerate(models, start=1):
        location = str(model.get("location", "active"))
        file_state = str(model.get("state", "unknown"))
        alias_count = len(model.get("aliases", []))
        status = f"{location}/{file_state}"
        print(f"{idx:<3} {status:<30} {_format_size(model.get('size_bytes')):<10} {alias_count:<7} {model['path']}")


def _print_aliases_only(aliases: list[dict[str, Any]], imported: dict[str, Any]) -> None:
    print("Aliases")
    print("ID   STATE     SECTION          MODEL")
    for alias in aliases:
        state = "enabled" if alias.get("enabled") else "disabled"
        print(f"{_alias_ref(imported, alias):<4} {state:<9} {alias['section']:<16} {alias['model_path']}")


def _server_discovery_payload(config: configparser.ConfigParser) -> dict[str, Any]:
    return _monitor_discovery_payload(config)


def _print_servers_only(config: configparser.ConfigParser) -> None:
    data = _server_discovery_payload(config)
    print("Servers")
    print(f"  found count: {data['found_count']}")
    if not data["candidates"]:
        print("  no server found through configured/default monitor discovery")
        return
    for candidate in data["candidates"]:
        state = "reachable" if candidate.get("reachable") else "not reachable"
        port = candidate.get("port") or "unknown"
        print(f"  - {port} {state} {candidate['endpoint']}")


def cmd_list(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    target = getattr(args, "target", None)
    show_active = getattr(args, "active", False)
    show_archived = getattr(args, "archived", False)
    show_enabled = getattr(args, "enabled", False)
    show_disabled = getattr(args, "disabled", False)
    if show_active and show_archived:
        print("Cannot combine --active and --archived", file=sys.stderr)
        return 2
    if show_enabled and show_disabled:
        print("Cannot combine --enabled and --disabled", file=sys.stderr)
        return 2

    models = imported.get("models", [])
    aliases_data = imported.get("aliases", [])
    filters_applied: dict[str, bool] = {}
    if show_active:
        models = [m for m in models if m.get("location", "active") == "active"]
        filters_applied["active"] = True
    elif show_archived:
        models = [m for m in models if m.get("location") == "archived"]
        filters_applied["archived"] = True
    if show_enabled:
        aliases_data = [a for a in aliases_data if a.get("enabled")]
        filters_applied["enabled"] = True
    elif show_disabled:
        aliases_data = [a for a in aliases_data if not a.get("enabled")]
        filters_applied["disabled"] = True

    kind = None
    if target:
        t = target.lower()
        if t in {"model", "models"}:
            kind = "models"
        elif t in {"alias", "aliases"}:
            kind = "aliases"
        elif t in {"server", "servers"}:
            kind = "servers"
        else:
            resolved = _resolve_target(imported, target)
            if not resolved.get("ok"):
                if getattr(args, "json", False):
                    payload = _target_error_payload(target, resolved.get("candidates"), resolved.get("suggestions"))
                    _print_json(_json_envelope("list", payload, status="error", error={"code": resolved.get("code"), "message": f"Could not resolve target: {target}"}))
                else:
                    _print_target_error(target, candidates=resolved.get("candidates"), suggestions=resolved.get("suggestions"))
                return 2
            if resolved["kind"] == "model":
                model_path = resolved["path"]
                aliases_for_model = [a for a in aliases_data if a.get("model_path") == model_path]
                if getattr(args, "json", False):
                    _print_json(_json_envelope("list", {"target": target, "resolved_target": resolved["resolved_target"], "aliases": [_candidate_for_alias(imported, a) for a in aliases_for_model]}))
                else:
                    print(f"Aliases for {model_path}")
                    _print_aliases_only(aliases_for_model, imported)
                return 0
            alias = resolved["alias"]
            if getattr(args, "json", False):
                _print_json(_json_envelope("list", {"target": target, "resolved_target": resolved["resolved_target"], "aliases": [_candidate_for_alias(imported, alias)]}))
            else:
                _print_aliases_only([alias], imported)
            return 0

    if getattr(args, "json", False):
        data: dict[str, Any] = {}
        if kind in (None, "models"):
            data["models"] = [{"id": idx, "path": m.get("path"), "state": m.get("state"), "location": m.get("location", "active"), "size_bytes": m.get("size_bytes"), "aliases": list(m.get("aliases", []))} for idx, m in enumerate(models, start=1)]
        if kind in (None, "aliases"):
            data["aliases"] = [{"id": f"a{idx}", "section": a.get("section"), "enabled": bool(a.get("enabled")), "model_path": a.get("model_path")} for idx, a in enumerate(aliases_data, start=1)]
        if kind in (None, "servers"):
            data["servers"] = _server_discovery_payload(config)
        if filters_applied:
            data["filters_applied"] = filters_applied
        _print_json(_json_envelope("list", data))
        return 0
    if kind == "models":
        _print_models_only(models); return 0
    if kind == "aliases":
        _print_aliases_only(aliases_data, imported); return 0
    if kind == "servers":
        _print_servers_only(config); return 0
    _print_models_only(models)
    print("")
    _print_aliases_only(aliases_data, imported)
    print("")
    _print_servers_only(config)
    return 0


def _target_key(value: str) -> str:
    """Case/separator-insensitive key; optional .gguf is ignored."""
    text = Path(str(value).strip()).name
    if text.lower().endswith(".gguf"):
        text = text[:-5]
    key = re.sub(r"[^a-z0-9]+", "", text.lower())
    for suffix in ("hyphen", "underscore"):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    return key


def _target_slug(value: str) -> str:
    text = Path(str(value).strip()).name
    if text.lower().endswith(".gguf"):
        text = text[:-5]
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _model_aliases(imported: dict[str, Any], model_path: str) -> list[dict[str, Any]]:
    return [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]


def _known_model_entries(imported: dict[str, Any]) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for model in imported.get("models", []):
        path = str(model.get("path") or "")
        if path:
            entries[path] = dict(model)
    for alias in imported.get("aliases", []):
        path = str(alias.get("model_path") or "")
        if path and path not in entries:
            entries[path] = {"path": path, "state": "present" if Path(path).expanduser().exists() else "missing", "location": "active", "aliases": []}
    for path in Path.cwd().glob("*.gguf"):
        key = str(path)
        if key not in entries:
            entries[key] = {"path": key, "state": "present", "location": "active", "aliases": []}
    return list(entries.values())


def _alias_ref(imported: dict[str, Any], alias: dict[str, Any]) -> str:
    try:
        return f"a{imported.get('aliases', []).index(alias) + 1}"
    except ValueError:
        return "a?"


def _model_ref(imported: dict[str, Any], model_path: str) -> str | None:
    for idx, model in enumerate(imported.get("models", []), start=1):
        if model.get("path") == model_path:
            return str(idx)
    return None


def _candidate_for_model(imported: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    path = str(model.get("path") or "")
    aliases = _model_aliases(imported, path)
    return {"type": "model", "ref": _model_ref(imported, path), "name": Path(path).name, "stem": Path(path).stem, "slug": _target_slug(path), "path": path, "location": model.get("location", "active"), "state": model.get("state", "unknown"), "aliases": [a.get("section") for a in aliases]}


def _candidate_for_alias(imported: dict[str, Any], alias: dict[str, Any]) -> dict[str, Any]:
    return {"type": "alias", "ref": _alias_ref(imported, alias), "name": alias.get("section"), "slug": _target_slug(str(alias.get("section") or "")), "section": alias.get("section"), "path": alias.get("model_path"), "model_path": alias.get("model_path"), "state": "enabled" if alias.get("enabled") else "disabled", "enabled": bool(alias.get("enabled"))}


def _format_candidate(candidate: dict[str, Any]) -> str:
    if candidate.get("type") == "alias":
        return f"{candidate.get('ref') or 'alias'}  {candidate.get('section')}  {candidate.get('state') or 'unknown'}  {candidate.get('model_path')}"
    return f"{candidate.get('ref') or 'model'}  {candidate.get('stem') or candidate.get('name')}  {candidate.get('location') or 'unknown'}  {candidate.get('path')}"


def _target_error_payload(target: str, candidates: list[dict[str, Any]] | None = None, suggestions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"target": target, "tried": ["alias/reference id", "alias/section name", "GGUF filename/stem", "relative/absolute path", "configured model/archive/download directories", "current directory"], "candidates": candidates or [], "suggestions": suggestions or []}


def _print_target_error(target: str, *, candidates: list[dict[str, Any]] | None = None, suggestions: list[dict[str, Any]] | None = None) -> None:
    if candidates:
        print(f"ambiguous target: {target}", file=sys.stderr)
        print("candidates:", file=sys.stderr)
        for candidate in candidates:
            print(f"  - {_format_candidate(candidate)}", file=sys.stderr)
    else:
        print(f"Could not resolve target: {target}", file=sys.stderr)
        print("Tried:", file=sys.stderr)
        path = Path(target)
        print(f"tried filename: {path.name}", file=sys.stderr)
        print(f"tried stem: {path.stem}", file=sys.stderr)
        print(f"tried path: {path}", file=sys.stderr)
        for item in _target_error_payload(target)["tried"]:
            print(f"  - {item}", file=sys.stderr)
        if suggestions:
            print("Closest matches:", file=sys.stderr)
            for suggestion in suggestions:
                print(f"  - {_format_candidate(suggestion)}", file=sys.stderr)
    print("Try:", file=sys.stderr)
    print("  modelctl list", file=sys.stderr)
    print(f"  modelctl show {target}", file=sys.stderr)


def _closest_candidates(imported: dict[str, Any], target: str, limit: int = 5) -> list[dict[str, Any]]:
    key = _target_key(target)
    if not key:
        return []
    scored: list[tuple[int, dict[str, Any]]] = []
    for alias in imported.get("aliases", []):
        cand = _candidate_for_alias(imported, alias)
        keys = [_target_key(str(alias.get("section") or "")), _target_key(str(cand.get("ref") or ""))]
        score = max((len(os.path.commonprefix([key, k])) for k in keys if k), default=0)
        if score:
            scored.append((score, cand))
    for model in _known_model_entries(imported):
        cand = _candidate_for_model(imported, model)
        keys = [_target_key(str(model.get("path") or "")), _target_key(Path(str(model.get("path") or "")).stem)]
        score = max((len(os.path.commonprefix([key, k])) for k in keys if k), default=0)
        if score:
            scored.append((score, cand))
    scored.sort(key=lambda item: item[0], reverse=True)
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _score, cand in scored:
        ident = (str(cand.get("type")), str(cand.get("path") or cand.get("section")))
        if ident in seen:
            continue
        seen.add(ident)
        result.append(cand)
        if len(result) >= limit:
            break
    return result


def _match_aliases(imported: dict[str, Any], target: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ref = target.split(":", 1)[1] if target.startswith("alias:") else target
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    ref_key = _target_key(ref)
    for idx, alias in enumerate(imported.get("aliases", []), start=1):
        section = str(alias.get("section") or "")
        names = {section, section.split(".")[-1], f"a{idx}"}
        if ref in names or (target.startswith("alias:") and ref == section):
            exact.append(alias)
            continue
        keys = {_target_key(name) for name in names if name}
        if ref_key and ref_key in keys:
            exact.append(alias)
        elif ref_key and any(ref_key in key for key in keys):
            partial.append(alias)
    return exact, partial


def _resolve_alias_target(imported: dict[str, Any], target: str) -> dict[str, Any] | None:
    exact, partial = _match_aliases(imported, target)
    matches = exact or partial
    return matches[0] if len(matches) == 1 else None


def _match_models(imported: dict[str, Any], target: str, *, prefer: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ref = target.split(":", 1)[1] if target.startswith(("model:", "path:")) else target
    ref_path = Path(ref).expanduser()
    ref_name = Path(ref).name
    ref_key = _target_key(ref)
    exact: list[dict[str, Any]] = []
    partial: list[dict[str, Any]] = []
    models = _known_model_entries(imported)
    for idx, model in enumerate(models, start=1):
        path = str(model.get("path") or "")
        p = Path(path).expanduser()
        if target.isdigit() and int(target) == idx:
            exact.append(model); continue
        if ref == path or ref_name in {Path(path).name, Path(path).stem}:
            exact.append(model); continue
        try:
            if (ref_path.is_absolute() or "/" in ref or ref.startswith(".")) and ref_path.resolve() == p.resolve():
                exact.append(model); continue
        except OSError:
            pass
        keys = {_target_key(x) for x in (path, Path(path).name, Path(path).stem) if x}
        if ref_key and ref_key in keys:
            exact.append(model)
        elif ref_key and any(ref_key in key for key in keys):
            partial.append(model)
    def sort_key(model: dict[str, Any]) -> tuple[int, str]:
        loc = model.get("location", "active")
        if prefer == "archived": pri = 0 if loc == "archived" else 1
        elif prefer == "active": pri = 0 if loc != "archived" else 1
        else: pri = 0
        return (pri, str(model.get("path") or ""))
    return sorted(exact, key=sort_key), sorted(partial, key=sort_key)


def _resolve_model_result(imported: dict[str, Any], target: str, *, prefer: str | None = None) -> dict[str, Any]:
    exact, partial = _match_models(imported, target, prefer=prefer)
    matches = exact or partial
    ref = target.split(":", 1)[1] if target.startswith(("model:", "path:")) else target
    ref_name = Path(ref).name
    if len(matches) > 1:
        case_exact = [m for m in matches if ref == str(m.get("path") or "") or ref_name == Path(str(m.get("path") or "")).name or ref_name == Path(str(m.get("path") or "")).stem]
        if len(case_exact) == 1:
            matches = case_exact
    if len(matches) > 1:
        aliased = [m for m in matches if _model_aliases(imported, str(m.get("path") or ""))]
        if len(aliased) == 1:
            matches = aliased
    if len(matches) > 1:
        gguf_matches = [m for m in matches if str(m.get("path") or "").lower().endswith(".gguf")]
        if len(gguf_matches) == 1:
            matches = gguf_matches
    if prefer and matches:
        preferred = [m for m in matches if (m.get("location") == "archived") == (prefer == "archived")]
        if len(preferred) == 1:
            matches = preferred
    if len(matches) == 1:
        return {"ok": True, "kind": "model", "path": matches[0]["path"], "model": matches[0], "resolved_target": _candidate_for_model(imported, matches[0])}
    if len(matches) > 1:
        return {"ok": False, "code": "ambiguous_target", "candidates": [_candidate_for_model(imported, m) for m in matches], "suggestions": []}
    return {"ok": False, "code": "target_not_found", "candidates": [], "suggestions": _closest_candidates(imported, target)}


def _resolve_model_target_with_candidates(imported: dict[str, Any], target: str) -> tuple[str | None, list[str] | None]:
    result = _resolve_model_result(imported, target)
    if result.get("ok"):
        return result["path"], None
    candidates = [c.get("path") for c in result.get("candidates", []) if c.get("path")]
    return None, candidates or None


def _resolve_model_target(imported: dict[str, Any], target: str) -> str | None:
    result = _resolve_model_result(imported, target)
    return str(result["path"]) if result.get("ok") else None


def _resolve_target(imported: dict[str, Any], target: str, *, prefer: str | None = None, alias_first: bool = False) -> dict[str, Any]:
    if alias_first:
        exact_aliases, partial_aliases = _match_aliases(imported, target)
        alias_matches = exact_aliases or partial_aliases
        if len(alias_matches) == 1:
            alias = alias_matches[0]
            return {"ok": True, "kind": "alias", "alias": alias, "resolved_target": _candidate_for_alias(imported, alias)}
        if len(alias_matches) > 1:
            return {"ok": False, "code": "ambiguous_target", "candidates": [_candidate_for_alias(imported, a) for a in alias_matches], "suggestions": []}
    model_result = _resolve_model_result(imported, target, prefer=prefer)
    if model_result.get("ok"):
        return model_result
    if not alias_first:
        exact_aliases, partial_aliases = _match_aliases(imported, target)
        alias_matches = exact_aliases or partial_aliases
        if len(alias_matches) == 1:
            alias = alias_matches[0]
            return {"ok": True, "kind": "alias", "alias": alias, "resolved_target": _candidate_for_alias(imported, alias)}
        if len(alias_matches) > 1:
            return {"ok": False, "code": "ambiguous_target", "candidates": [_candidate_for_alias(imported, a) for a in alias_matches], "suggestions": []}
    return model_result

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
    resolved = _resolve_target(imported, args.target)
    if not resolved.get("ok"):
        if getattr(args, "json", False):
            _print_json(_json_envelope("show", {}, status="error", error={"code": resolved.get("code"), "message": f"Could not resolve target: {args.target}", "details": _target_error_payload(args.target, resolved.get("candidates"), resolved.get("suggestions"))}))
            return 2
        _print_target_error(args.target, candidates=resolved.get("candidates"), suggestions=resolved.get("suggestions"))
        return 2
    if resolved["kind"] == "alias":
        alias = resolved["alias"]
        if getattr(args, "json", False):
            _print_json(_json_envelope("show", {"target": args.target, "resolved_target": resolved["resolved_target"], "alias": {"ref": _alias_ref(imported, alias), "section": alias["section"], "state": "enabled" if alias.get("enabled") else "disabled", "enabled": bool(alias.get("enabled")), "model_path": alias["model_path"], "model_filename": Path(alias["model_path"]).name, "model_stem": Path(alias["model_path"]).stem, "params": alias.get("params", {})}}))
            return 0
        state = "enabled" if alias.get("enabled") else "disabled"
        print("Alias")
        print(f"  ref: {_alias_ref(imported, alias)}")
        print(f"  section: {alias['section']}")
        print(f"  state: {state}")
        print(f"  model: {alias['model_path']}")
        print(f"  model filename: {Path(alias['model_path']).name}")
        print(f"  model stem: {Path(alias['model_path']).stem}")
        print("  params:")
        for key, value in sorted(alias.get("params", {}).items()):
            print(f"    {key}: {value}")
        return 0
    model_path = resolved["path"]
    aliases = [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]
    key = _hf_key_for_alias(aliases[0]) if aliases else None
    hf_state = _load_json(_state_dir() / 'hf-status.json') or {}
    benchmark = _load_json(_benchmark_file(config, model_path))
    gpu_vram_bytes = _gpu_vram_bytes(args)
    if getattr(args, "json", False):
        model = next((m for m in _known_model_entries(imported) if m["path"] == model_path), None)
        guidance = _estimate_model_guidance(model, gpu_vram_bytes=gpu_vram_bytes, benchmark=benchmark, hf_status=hf_state.get(key) if key else None)
        aliases_data = [{"ref": _alias_ref(imported, a), "section": a["section"], "state": "enabled" if a.get("enabled") else "disabled", "enabled": bool(a.get("enabled"))} for a in aliases]
        model_data = {"path": model_path, "filename": Path(model_path).name, "stem": Path(model_path).stem, "aliases": aliases_data, "referenced_by_enabled_aliases": any(a.get("enabled") for a in aliases), "referenced_by_disabled_aliases": any(not a.get("enabled") for a in aliases), "guidance": guidance}
        if model:
            model_data.update(state=model.get("state"), location=model.get("location", "active"), size_bytes=model.get("size_bytes"))
        _print_json(_json_envelope("show", {"target": args.target, "resolved_target": resolved["resolved_target"], "model": model_data}))
        return 0
    _print_model_details(imported, model_path, gpu_vram_bytes=gpu_vram_bytes, benchmark=benchmark, hf_status=hf_state.get(key) if key else None)
    return 0

def cmd_aliases(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    model_path = _resolve_model_target(imported, args.target)
    if model_path is None:
        if getattr(args, "json", False):
            _print_json(_json_envelope("aliases", status="error", error={"code": "target_not_found", "message": f"Could not resolve model target: {args.target}"}))
            return 2
        print(f"Could not resolve model target: {args.target}", file=sys.stderr)
        print("Try: modelctl list", file=sys.stderr)
        return 2
    aliases = [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]
    if getattr(args, "json", False):
        aliases_data = [
            {
                "section": a["section"],
                "state": "enabled" if a.get("enabled") else "disabled",
                "enabled": bool(a.get("enabled")),
            }
            for a in aliases
        ]
        _print_json(_json_envelope("aliases", {
            "target": args.target,
            "resolved_target": model_path,
            "model_path": model_path,
            "aliases": aliases_data,
        }))
        return 0
    print(f"Aliases for {model_path}")
    for alias in aliases:
        state = "enabled" if alias.get("enabled") else "disabled"
        print(f"  - {alias['section']} ({state})")
    return 0


def cmd_doctor(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    router_ini = Path(config.get("router", "ini")).expanduser()
    registry = Path(config.get("state", "registry", fallback=str(Path(args.config).with_name("modelctl.yaml")))).expanduser()
    exit_code = 0
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    def check(name: str, status: str, *, path: Path | str | None = None, detail: str | None = None) -> None:
        item: dict[str, Any] = {"name": name, "status": status}
        if path is not None:
            item["path"] = str(path)
        if detail is not None:
            item["detail"] = detail
        checks.append(item)

    if router_ini.exists() and router_ini.is_file():
        check("router_ini", "ok", path=router_ini)
        imported = _import_from_config(config)
        check("aliases", "ok", detail=str(len(imported["aliases"])))
        check("models", "ok", detail=str(len(imported["models"])))
        archived_count = sum(1 for model in imported.get("models", []) if model.get("location") == "archived")
        if archived_count:
            check("archived_models", "ok", detail=str(archived_count))
    else:
        check("router_ini", "error", path=router_ini, detail="missing")
        imported = {"aliases": [], "models": []}
        exit_code = 1

    try:
        registry.parent.mkdir(parents=True, exist_ok=True)
        probe = registry.parent / ".modelctl-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check("registry_writable", "ok", path=registry)
    except OSError as exc:
        check("registry_writable", "error", path=registry, detail=str(exc))
        exit_code = 1

    download_dir = config.get("models", "download_dir", fallback=None) or imported.get("download_dir")
    if download_dir:
        p = Path(download_dir).expanduser()
        if p.exists() and p.is_dir():
            check("download_dir", "ok", path=p)
        else:
            check("download_dir", "warning", path=p, detail="missing")
            warnings.append("download_dir_missing")
    else:
        check("download_dir", "warning", detail="unknown")
        warnings.append("download_dir_unknown")
    paths = {
        "config_dir": str(_config_dir()),
        "data_dir": str(_data_dir()),
        "state_dir": str(_state_dir()),
        "cache_dir": str(_cache_dir()),
        "recovery_dir": str(_recovery_dir(config)),
        "benchmark_dir": str(_benchmark_dir(config)),
    }
    safety = {
        "delete_requires_tty_confirmation": True,
        "archive_apply_supports_dry_run": True,
    }
    if getattr(args, "json", False):
        _print_json(_json_envelope(
            "doctor",
            {"checks": checks, "paths": paths, "safety": safety},
            status="ok" if exit_code == 0 else "error",
            warnings=warnings,
            error={"code": "doctor_failed", "message": "one or more checks failed"} if exit_code else None,
        ))
        return exit_code
    for item in checks:
        status = item["status"].upper()
        path = f": {item['path']}" if "path" in item else ""
        detail = f" ({item['detail']})" if "detail" in item else ""
        print(f"{status} {item['name']}{path}{detail}")
    for name, value in paths.items():
        print(f"OK {name.replace('_', ' ')}: {value}")
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
        if getattr(args, "json", False) and not getattr(args, "apply", False):
            _print_json(_json_envelope("delete", {}, status="error",
                error={"code": "target_not_found", "message": f"Could not resolve model target: {args.target}"}))
            return 2
        print(f"Could not resolve model target: {args.target}", file=sys.stderr)
        print("Try: modelctl list", file=sys.stderr)
        return 2
    plan = plan_delete_model(imported, model_path)
    if args.dry_run:
        if getattr(args, "json", False):
            alias_sections = [{"section": a["section"], "enabled": a.get("enabled")} for a in plan.get("aliases", [])]
            planned_recovery = str(_default_recovery_path(args.config, config))
            data: dict[str, Any] = {
                "target": args.target,
                "dry_run": True,
                "model_path": model_path,
                "affected_aliases": plan.get("aliases_impacted", []),
                "affected_sections": plan.get("aliases_impacted", []),
                "planned_recovery_manifest_path": planned_recovery,
                "planned_changes": [f"delete {Path(model_path).name}"] + [f"remove alias [{s}]" for s in plan.get("aliases_impacted", [])],
                "would_delete_file": False,
                "would_update_ini": False,
                "would_write_recovery_manifest": False,
                "delete_requires_apply": True,
            }
            _print_json(_json_envelope("delete", data, warnings=plan.get("warnings")))
            return 0
        _print_delete_plan(plan, dry_run=True)
        print("No files or ini entries were changed.")
        return 0
    _print_delete_plan(plan, dry_run=False)
    if not getattr(args, "apply", False) and not _confirm_delete_interactively(plan):
        print("Delete cancelled. No files or ini entries were changed.")
        return 1
    manifest_path = _default_recovery_path(args.config, config)
    try:
        result = apply_delete_plan(plan, manifest_path=manifest_path)
    except Exception as exc:
        if getattr(args, "json", False):
            _print_json(_json_envelope("delete", {}, status="error",
                error={"code": "delete_failed", "message": str(exc)}))
        else:
            print(f"delete failed safely: {exc}", file=sys.stderr)
        return 1
    print(f"APPLIED: deleted {len(result['deleted_files'])} file(s) and removed {len(plan['aliases_impacted'])} alias section(s)")
    print(f"  recovery manifest: {result['recovery_manifest']}")
    return 0


def _default_plan_path(config_path: str, prefix: str = "archive") -> Path:
    stamp = _utc_now().replace(":", "").replace("-", "")
    return _state_dir() / "plans" / f"{prefix}-{stamp}.json"


def _default_recovery_path(config_path: str, config: configparser.ConfigParser | None = None, prefix: str = "delete") -> Path:
    stamp = _utc_now().replace(":", "").replace("-", "")
    return _recovery_dir(config) / f"{prefix}-{stamp}.json"


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
    resolved_meta: list[dict[str, Any]] = []
    for target in args.target:
        resolved = _resolve_target(imported, target, prefer="active")
        if not resolved.get("ok"):
            if getattr(args, "json", False):
                args._target_error = resolved
            else:
                _print_target_error(target, candidates=resolved.get("candidates"), suggestions=resolved.get("suggestions"))
            return None
        if resolved["kind"] == "alias":
            alias = resolved["alias"]
            model_path = alias.get("model_path")
            meta = _candidate_for_alias(imported, alias)
        else:
            model_path = resolved["path"]
            meta = resolved["resolved_target"]
        if not model_path:
            return None
        targets.append(model_path)
        resolved_meta.append(meta)
    args._resolved_targets = resolved_meta
    return targets

def cmd_archive(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    targets = _archive_targets(args, imported)
    if targets is None:
        if getattr(args, 'json', False):
            err = getattr(args, "_target_error", {}) or {}
            payload = _target_error_payload(" ".join(getattr(args, "target", []) or []), err.get("candidates"), err.get("suggestions"))
            _print_json(_json_envelope("archive", payload, status="error",
                error={"code": err.get("code", "target_not_found"), "message": "Could not resolve archive target(s)"}))
        return 2
    plan = plan_archive_models(imported, targets, disable_aliases=bool(getattr(args, "disable_aliases", False)))
    if getattr(args, 'dry_run', False):
        if getattr(args, 'json', False):
            data = {
                "targets": targets,
                "resolved_target": getattr(args, "_resolved_targets", []),
                "dry_run": True,
                "would_move_file": False,
                "would_update_ini": False,
                "aliases_preserved": plan["aliases_policy"] == "preserve",
                "disable_aliases": bool(getattr(args, "disable_aliases", False)),
                "affected_aliases": [],
                "entries": [],
                "planned_changes": [],
                "metadata_path": None,
            }
            for entry in plan["entries"]:
                action = "preserve" if plan["aliases_policy"] == "preserve" else "disable"
                data["entries"].append({
                    "source_path": entry["source"],
                    "archive_path": entry["destination"],
                    "aliases_impacted": entry["aliases_impacted"],
                })
                data["affected_aliases"].extend(entry["aliases_impacted"])
                data["planned_changes"].append(
                    f"move {Path(entry['source']).name} to archive"
                )
                if entry["aliases_impacted"]:
                    data["planned_changes"].append(
                        f"{action} {len(entry['aliases_impacted'])} alias(es)"
                    )
            _print_json(_json_envelope("archive", data, warnings=plan.get("warnings")))
            return 0
        _print_archive_plan(plan, dry_run=True)
        print("No files or ini entries were changed. Re-run without --dry-run to apply this exact archive plan.")
        return 0
    plan_path = Path(args.plan).expanduser() if args.plan else _default_plan_path(args.config)
    try:
        applied = apply_archive_plan(plan, plan_path=plan_path)
    except Exception as exc:
        if getattr(args, 'json', False):
            _print_json(_json_envelope("archive", {}, status="error",
                error={"code": "archive_failed", "message": str(exc)}))
        else:
            print(f"archive failed safely: {exc}", file=sys.stderr)
        return 1
    if getattr(args, 'json', False):
        entries_data = []
        affected = []
        for entry in applied.get("entries", []):
            entries_data.append({
                "source_path": entry.get("source"),
                "archive_path": entry.get("destination"),
                "aliases_impacted": entry.get("aliases_impacted", []),
            })
            affected.extend(entry.get("aliases_impacted", []))
        _print_json(_json_envelope("archive", {
            "targets": targets,
            "resolved_target": getattr(args, "_resolved_targets", []),
            "applied": True,
            "dry_run": False,
            "moved": applied.get("moved", []),
            "entries": entries_data,
            "affected_aliases": affected,
            "aliases_preserved": applied.get("aliases_policy") == "preserve",
            "disable_aliases": bool(getattr(args, "disable_aliases", False)),
            "ini_path": config.get("router", "ini"),
            "metadata_path": str(plan_path),
            "router_ini_backup": applied.get("router_ini_backup"),
        }, warnings=applied.get("warnings")))
        return 0
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
    if not args.target:
        print("usage: modelctl update-check TARGET", file=sys.stderr)
        print("Try: modelctl list", file=sys.stderr)
        return 2
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
    resolved = _resolve_target(imported, args.target, alias_first=True)
    if not resolved.get("ok"):
        if getattr(args, "json", False):
            payload = _target_error_payload(args.target, resolved.get("candidates"), resolved.get("suggestions"))
            _print_json(_json_envelope("enable" if enable else "disable", payload, status="error", error={"code": resolved.get("code"), "message": f"Could not resolve target: {args.target}"}))
            return 2
        _print_target_error(args.target, candidates=resolved.get("candidates"), suggestions=resolved.get("suggestions"))
        return 2
    if resolved["kind"] == "alias":
        aliases = [resolved["alias"]]
    else:
        aliases = _model_aliases(imported, resolved["path"])
        if not aliases:
            msg = f"No aliases point to model target: {args.target}"
            if getattr(args, "json", False):
                _print_json(_json_envelope("enable" if enable else "disable", {"target": args.target, "resolved_target": resolved["resolved_target"], "affected_aliases": [], "changed_count": 0}, status="error", error={"code": "no_aliases", "message": msg}))
                return 2
            print(msg, file=sys.stderr)
            return 2
    action = "enable" if enable else "disable"
    affected = [_candidate_for_alias(imported, a) for a in aliases]
    if getattr(args, 'dry_run', False):
        if getattr(args, "json", False):
            _print_json(_json_envelope(action, {"target": args.target, "resolved_target": resolved["resolved_target"], "dry_run": True, "affected_aliases": affected, "changed_count": len(aliases), "would_update_ini": False}))
            return 0
        print(f"DRY RUN: would {action} {len(aliases)} alias(es) in router ini")
        for alias in aliases:
            print(f"  - [{alias['section']}] -> {alias['model_path']}")
        print("No ini entries were changed.")
        return 0
    router_ini = Path(config.get('router', 'ini')).expanduser()
    changed_count = 0
    for alias in aliases:
        if _rewrite_alias_block(router_ini, alias['section'], enable=enable):
            changed_count += 1
    if getattr(args, "json", False):
        _print_json(_json_envelope(action, {"target": args.target, "resolved_target": resolved["resolved_target"], "applied": True, "dry_run": False, "affected_aliases": affected, "changed_count": changed_count, "ini_path": str(router_ini)}))
        return 0
    print(f"APPLIED: {action}d {changed_count} alias(es) in {router_ini}" + ("" if changed_count else " (already in requested state)"))
    for alias in aliases:
        print(f"  - [{alias['section']}] -> {alias['model_path']}")
    return 0

def cmd_add_entry(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    router_ini = Path(config.get("router", "ini")).expanduser()
    if getattr(args, 'dry_run', False):
        if getattr(args, 'json', False):
            planned_changes = [
                f"append section [{args.alias}] to router ini",
                f"set model = {args.model}",
                "set ctx-size = 65536",
                "set n-gpu-layers = 999",
                "set flash-attn = on",
            ]
            _print_json(_json_envelope("add", {
                "target_path": str(router_ini),
                "alias": args.alias,
                "model_path": args.model,
                "dry_run": True,
                "would_write_ini": False,
                "planned_changes": planned_changes,
            }))
            return 0
        print("Router ini entry plan with estimated best defaults")
        print(f"  alias: {args.alias}")
        print(f"  model: {args.model}")
        print("  estimated flags: ctx-size = 65536, n-gpu-layers = 999, flash-attn = true")
        print("No ini entries were changed.")
        return 0
    if not getattr(args, 'json', False):
        print("Router ini entry plan with estimated best defaults")
        print(f"  alias: {args.alias}")
        print(f"  model: {args.model}")
        print("  estimated flags: ctx-size = 65536, n-gpu-layers = 999, flash-attn = true")
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
    if getattr(args, 'json', False):
        _print_json(_json_envelope("add", {
            "applied": True,
            "dry_run": False,
            "alias": args.alias,
            "model_path": args.model,
            "ini_path": str(router_ini),
        }))
        return 0
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


def _archive_metadata_dirs(config_path: str) -> list[Path]:
    config_file = Path(config_path).expanduser()
    dirs = [config_file.with_name("plans")]
    state_plans = _state_dir() / "plans"
    state_archive = _state_dir() / "archive"
    for directory in (state_plans, state_archive):
        if directory not in dirs:
            dirs.append(directory)
    return dirs


def _find_archive_metadata(config_path: str, archived_path: str) -> dict[str, Any] | None:
    for directory in _archive_metadata_dirs(config_path):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json"), reverse=True):
            payload = _load_json(path)
            if not isinstance(payload, dict) or payload.get("action") != "archive_models":
                continue
            for entry in payload.get("entries", []):
                if entry.get("destination") == archived_path:
                    return payload
    return None


def _active_restore_path(config: configparser.ConfigParser, archived_path: str, metadata: dict[str, Any] | None) -> str:
    if metadata:
        for entry in metadata.get("entries", []):
            if entry.get("destination") == archived_path and entry.get("source"):
                return str(Path(entry["source"]).expanduser())
    download_dir = config.get("models", "download_dir", fallback=None)
    if not download_dir:
        return str(Path(archived_path).expanduser().name)
    return str(Path(download_dir).expanduser() / Path(archived_path).name)


def _restore_plan(config: configparser.ConfigParser, config_path: str, target: str) -> dict[str, Any]:
    imported = _import_from_config(config)
    resolved = _resolve_model_result(imported, target, prefer="archived")
    archived_path = resolved["path"] if resolved.get("ok") else (target.split(":", 1)[1] if target.startswith("path:") else target)
    archived = Path(archived_path).expanduser()
    metadata = _find_archive_metadata(config_path, str(archived))
    active = Path(_active_restore_path(config, str(archived), metadata)).expanduser()
    warnings: list[str] = []
    if not archived.exists():
        warnings.append(f"archive source missing: {archived}")
    if active.exists():
        warnings.append(f"target active file already exists: {active}")
    reenable_aliases = False
    if metadata:
        reenable_aliases = metadata.get("aliases_policy") == "disable"
    return {
        "version": 1,
        "action": "restore_models",
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "router_ini": config.get("router", "ini"),
        "entries": [
            {
                "source": str(archived),
                "destination": str(active),
                "reenable_aliases": reenable_aliases,
                "metadata_found": bool(metadata),
            }
        ],
        "warnings": warnings,
        "requires_confirmation": False,
    }


def _print_restore_plan(plan: dict[str, Any], dry_run: bool) -> None:
    print("DRY RUN: restore model impact preview" if dry_run else "APPLIED: restore model")
    print(f"  router ini: {plan['router_ini']}")
    for idx, entry in enumerate(plan.get("entries", []), start=1):
        print(f"  model {idx}:")
        print(f"    archive source: {entry['source']}")
        print(f"    active destination: {entry['destination']}")
        print(f"    re-enable aliases: {entry.get('reenable_aliases', False)}")
    for warning in plan.get("warnings", []):
        print(f"  warning: {warning}")


def cmd_restore(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    plan = _restore_plan(config, args.config, args.target)
    if getattr(args, "dry_run", False):
        if getattr(args, "json", False):
            entry = plan["entries"][0]
            data: dict[str, Any] = {
                "target": args.target,
                "dry_run": True,
                "archive_path": entry["source"],
                "source_path": entry["source"],
                "active_path": entry["destination"],
                "restore_path": entry["destination"],
                "affected_aliases": [],
                "planned_changes": [f"restore {Path(entry['source']).name} to active storage"],
                "would_move_file": False,
                "would_update_ini": False,
            }
            if entry.get("reenable_aliases"):
                metadata = _find_archive_metadata(args.config, entry["source"])
                if metadata:
                    for me in metadata.get("entries", []):
                        if me.get("destination") == entry["source"]:
                            data["affected_aliases"] = me.get("aliases_impacted", [])
                            break
                if not data["affected_aliases"]:
                    data["planned_changes"].append("re-enable aliases after restore")
            _print_json(_json_envelope("restore", data, warnings=plan.get("warnings")))
            return 0
        _print_restore_plan(plan, dry_run=True)
        print("No files or ini entries were changed. Re-run without --dry-run to restore.")
        return 0
    try:
        applied = apply_restore_plan(plan)
    except Exception as exc:
        if getattr(args, 'json', False):
            _print_json(_json_envelope("restore", {}, status="error",
                error={"code": "restore_failed", "message": str(exc)}))
        else:
            print(f"restore failed safely: {exc}", file=sys.stderr)
        return 1
    if getattr(args, 'json', False):
        restored_entries = []
        affected_aliases = []
        for entry in applied.get("entries", []):
            restored_entries.append({
                "source": entry.get("source"),
                "destination": entry.get("destination"),
            })
            if entry.get("reenable_aliases"):
                metadata = _find_archive_metadata(args.config, entry.get("source"))
                if metadata:
                    for me in metadata.get("entries", []):
                        if me.get("destination") == entry.get("source"):
                            affected_aliases = me.get("aliases_impacted", [])
                            break
        _print_json(_json_envelope("restore", {
            "target": args.target,
            "applied": True,
            "dry_run": False,
            "restored": restored_entries,
            "affected_aliases": affected_aliases,
            "ini_path": config.get("router", "ini"),
            "router_ini_backup": applied.get("router_ini_backup"),
        }, warnings=applied.get("warnings")))
        return 0
    _print_restore_plan(applied, dry_run=False)
    print("Restore applied. Router ini backup was written and unrelated ini content was preserved.")
    return 0

def cmd_recover(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    manifest_path = Path(args.manifest).expanduser()
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        if getattr(args, 'json', False):
            _print_json(_json_envelope("recover", {}, status="error",
                error={"code": "manifest_not_found", "message": f"could not read recovery manifest: {manifest_path}"}))
        else:
            print(f"recover failed safely: could not read recovery manifest: {manifest_path}", file=sys.stderr)
        return 1
    if getattr(args, "dry_run", False):
        if getattr(args, "json", False):
            model_path = manifest.get("deleted_model_path", "")
            affected_aliases = [a.get("section") for a in manifest.get("affected_aliases", []) if a.get("section")]
            affected_sections = [s.get("section") for s in manifest.get("affected_sections", []) if s.get("section")]
            router_ini_path = Path(config.get("router", "ini")).expanduser()
            imported = _import_from_config(config)
            existing_sections = {a.get("section") for a in imported.get("aliases", [])}
            conflicts = [s for s in affected_sections if s in existing_sections]
            data: dict[str, Any] = {
                "recovery_manifest_path": str(manifest_path),
                "dry_run": True,
                "model_path": model_path,
                "affected_aliases": affected_aliases,
                "affected_sections": affected_sections,
                "planned_changes": [f"restore {len(affected_sections)} section(s) to router ini"],
                "would_update_ini": False,
                "conflict_status": {"has_conflicts": bool(conflicts), "conflicting_sections": conflicts},
            }
            _print_json(_json_envelope("recover", data, warnings=[]))
            return 0
        print("DRY RUN: recover delete manifest")
        print(f"  manifest: {manifest_path}")
        print(f"  model: {manifest.get('deleted_model_path')}")
        print(f"  sections to restore: {len(manifest.get('affected_sections', []))}")
        return 0
    affected_aliases = [a.get("section") for a in manifest.get("affected_aliases", []) if a.get("section")]
    affected_sections = [s.get("section") for s in manifest.get("affected_sections", []) if s.get("section")]
    router_ini_path = Path(config.get("router", "ini")).expanduser()
    imported_before = _import_from_config(config)
    section_conflicts = [s for s in affected_sections if s in {a.get("section") for a in imported_before.get("aliases", [])}]
    try:
        result = apply_recover_manifest(manifest, router_ini=config.get("router", "ini"))
    except Exception as exc:
        if getattr(args, 'json', False):
            conf = {"has_conflicts": bool(section_conflicts), "conflicting_sections": section_conflicts}
            _print_json(_json_envelope("recover", {
                "recovery_manifest_path": str(manifest_path),
                "conflict_status": conf,
            }, status="error",
                error={"code": "recover_failed", "message": str(exc)}))
        else:
            print(f"recover failed safely: {exc}", file=sys.stderr)
        return 1
    if getattr(args, 'json', False):
        _print_json(_json_envelope("recover", {
            "recovery_manifest_path": str(manifest_path),
            "applied": True,
            "dry_run": False,
            "model_path": manifest.get("deleted_model_path", ""),
            "sections_restored": result.get("sections", []),
            "affected_aliases": affected_aliases,
            "ini_path": str(router_ini_path),
            "conflict_status": {"has_conflicts": bool(section_conflicts), "conflicting_sections": section_conflicts},
        }))
        return 0
    print("APPLIED: recovered delete manifest")
    print(f"  router ini: {result['router_ini']}")
    print(f"  sections restored: {len(result['sections'])}")
    for section in result["sections"]:
        print(f"    - {section}")
    return 0


def _monitor_discovery_endpoints(config: configparser.ConfigParser) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    configured_values: list[str] = []
    for option in ("endpoint", "base_url", "url"):
        value = config.get("monitor", option, fallback="").strip()
        if value:
            configured_values.append(value)
    endpoints_value = config.get("monitor", "endpoints", fallback="").strip()
    if endpoints_value:
        configured_values.extend(x.strip() for x in re.split(r"[,\n]", endpoints_value) if x.strip())
    for endpoint in configured_values:
        candidates.append({"endpoint": endpoint.rstrip("/"), "source": "configured"})
    include_defaults = config.getboolean("monitor", "discover_defaults", fallback=True)
    if include_defaults:
        candidates.extend([
            {"endpoint": "http://127.0.0.1:8080/v1", "source": "default_loopback"},
            {"endpoint": "http://localhost:8080/v1", "source": "default_localhost"},
        ])
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for candidate in candidates:
        endpoint = candidate["endpoint"].rstrip("/")
        if endpoint in seen:
            continue
        seen.add(endpoint)
        unique.append({"endpoint": endpoint, "source": candidate["source"]})
    return unique


def _models_endpoint(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    return f"{endpoint}/models" if endpoint.endswith("/v1") else f"{endpoint}/v1/models"


def _endpoint_port(endpoint: str) -> str:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.port is not None:
        return str(parsed.port)
    if parsed.scheme == "https":
        return "443"
    if parsed.scheme == "http":
        return "80"
    return "unknown"


def _summarize_current_model(model_ids: list[str]) -> str:
    if len(model_ids) == 1:
        return model_ids[0]
    return "unknown"


def _enrich_monitor_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    model_ids = [str(model_id) for model_id in candidate.get("model_ids", [])]
    enriched = dict(candidate)
    enriched["port"] = _endpoint_port(str(candidate.get("endpoint", "")))
    enriched["service"] = "unknown"
    enriched["available_model_count"] = len(model_ids)
    enriched["current_model"] = _summarize_current_model(model_ids)
    return enriched


def _query_models_endpoint(endpoint: str, timeout: float) -> dict[str, Any]:
    models_endpoint = _models_endpoint(endpoint)
    result: dict[str, Any] = {"endpoint": endpoint.rstrip("/"), "reachable": False, "models_endpoint": models_endpoint, "model_ids": [], "error_message": None}
    try:
        request = urllib.request.Request(models_endpoint, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(1024 * 1024)
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        data = payload.get("data", payload) if isinstance(payload, dict) else payload
        model_ids: list[str] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("id") is not None:
                    model_ids.append(str(item["id"]))
                elif isinstance(item, str):
                    model_ids.append(item)
        result["reachable"] = True
        result["model_ids"] = model_ids
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        result["error_message"] = str(exc)
    return _enrich_monitor_candidate(result)


def _monitor_discovery_payload(config: configparser.ConfigParser) -> dict[str, Any]:
    timeout = config.getfloat("monitor", "discovery_timeout", fallback=0.5)
    candidates = []
    for candidate in _monitor_discovery_endpoints(config):
        probed = _query_models_endpoint(candidate["endpoint"], timeout)
        probed["source"] = candidate["source"]
        candidates.append(probed)
    reachable = [candidate for candidate in candidates if candidate["reachable"]]
    return {"candidates": candidates, "found_count": len(reachable), "selected": reachable[0]["endpoint"] if len(reachable) == 1 else None, "mutated": False}


def _print_monitor_candidate(candidate: dict[str, Any]) -> None:
    port = candidate.get("port") or "unknown"
    state = "reachable" if candidate.get("reachable") else "not reachable"
    print(f"{port}  {state}  {candidate['endpoint']}")
    print(f"service: {candidate.get('service') or 'unknown'}")
    print(f"current model: {candidate.get('current_model') or 'unknown'}")
    print(f"available models: {candidate.get('available_model_count', 0)}")
    if candidate.get("error_message"):
        print(f"error: {candidate['error_message']}")


def _print_monitor_try_commands(candidates: list[dict[str, Any]]) -> None:
    ports = [candidate.get("port") for candidate in candidates if candidate.get("reachable") and candidate.get("port") not in {None, "", "unknown"}]
    if not ports:
        return
    print()
    print("Try:")
    for port in ports:
        print(f"modelctl monitor {port}")
    for port in ports:
        print(f"modelctl tail {port}")
        print(f"modelctl restart {port}")


def cmd_monitor_discover(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    data = _monitor_discovery_payload(config)
    reachable = [candidate for candidate in data["candidates"] if candidate["reachable"]]
    warnings: list[str] = []
    if len(reachable) > 1:
        warnings.append("multiple servers found; explicit selection/configuration is required")
    elif not reachable:
        warnings.append("no server found; provide endpoint or log details")
    if getattr(args, "json", False):
        _print_json(_json_envelope("monitor discover", data, warnings=warnings))
        return 0
    print("Monitor discovery (read-only)")
    print(f"found count: {len(reachable)}")
    if not data["candidates"]:
        print()
        print("No servers were checked.")
        return 0
    if not reachable:
        print()
        print("No local llama server responded.")
    for candidate in data["candidates"]:
        print()
        _print_monitor_candidate(candidate)
    _print_monitor_try_commands(reachable)
    return 0


def _monitor_candidate_for_port(config: configparser.ConfigParser, port: str) -> dict[str, Any] | None:
    data = _monitor_discovery_payload(config)
    for candidate in data["candidates"]:
        if str(candidate.get("port")) == str(port):
            return candidate
    return None


def cmd_monitor(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    target = getattr(args, "target", "router")
    if target == "discover":
        return cmd_monitor_discover(args, config)
    lines_requested = max(int(getattr(args, "lines", 80) or 80), 0)
    follow = bool(getattr(args, "follow", False))
    as_json = bool(getattr(args, "json", False))
    if str(target).isdigit():
        candidate = _monitor_candidate_for_port(config, str(target))
        if candidate is None:
            payload = {
                "target": target,
                "mode": "read-only",
                "status": "not_found",
                "error": f"no discovered local llama server matches port {target}; run modelctl monitor discover",
                "suggested_commands": ["modelctl monitor discover"],
            }
            if as_json:
                _print_json(_json_envelope("monitor", payload, status="error", error={"code": "monitor_failed", "message": payload["error"]}))
            else:
                print(payload["error"], file=sys.stderr)
            return 2
        payload = {"target": target, "mode": "read-only", "status": "ok", "server": candidate, "follow": follow, "lines_requested": lines_requested}
        if as_json:
            _print_json(_json_envelope("monitor", payload))
        else:
            print("Server monitor")
            print(f"port: {candidate.get('port')}")
            print(f"endpoint: {candidate.get('endpoint')}")
            print(f"reachable: {str(bool(candidate.get('reachable'))).lower()}")
            print(f"service: {candidate.get('service') or 'unknown'}")
            print(f"current model: {candidate.get('current_model') or 'unknown'}")
            print(f"available models: {candidate.get('available_model_count', 0)}")
        return 0
    backend = config.get("monitor", "backend", fallback="none").strip().lower() or "none"
    payload: dict[str, Any] = {"target": target, "backend": backend, "follow": follow, "lines_requested": lines_requested, "mode": "read-only"}
    def finish(code: int) -> int:
        flush = bool(payload.get("follow"))
        if as_json:
            error = None
            if code != 0:
                error = {"code": "monitor_failed", "message": str(payload.get("error") or "monitor failed")}
            _print_json(_json_envelope("monitor", payload, status="ok" if code == 0 else "error", error=error))
        else:
            if code == 0:
                print("Router monitor", flush=flush)
                print("  mode: read-only", flush=flush)
                print(f"  target: {payload.get('target')}", flush=flush)
                print(f"  backend: {payload.get('backend')}", flush=flush)
                if payload.get("log_file"):
                    print(f"  log file: {payload['log_file']}", flush=flush)
                if payload.get("service"):
                    print(f"  service: {payload['service']}", flush=flush)
                for line in payload.get("lines", []):
                    print(line, flush=flush)
            else:
                print(str(payload.get("error") or "monitor failed"), file=sys.stderr, flush=True)
        return code

    if target != "router":
        payload["error"] = f"unsupported monitor target: {target}"
        return finish(2)
    if backend == "none":
        payload["status"] = "unconfigured"
        payload["suggested_commands"] = ["modelctl monitor discover"]
        payload["next_steps"] = [
            "Run modelctl monitor discover to probe common local endpoints without changing files.",
            "Configure [monitor] backend=file with log_file, or provide endpoint/log details in the config.",
        ]
        payload["error"] = (
            "monitor backend is not configured; run modelctl monitor discover "
            "or set [monitor] backend=file with log_file / endpoint details"
        )
        return finish(2)
    if backend == "file":
        log_file = config.get("monitor", "log_file", fallback="").strip()
        payload["log_file"] = log_file
        if not log_file:
            payload["status"] = "unconfigured"
            payload["error"] = "monitor backend=file requires [monitor] log_file"
            return finish(2)
        path = Path(log_file).expanduser()
        if not path.exists():
            payload["status"] = "missing"
            payload["error"] = f"configured log file does not exist: {path}"
            return finish(1)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            payload["status"] = "error"
            payload["error"] = f"failed to read configured log file: {exc}"
            return finish(1)
        payload["status"] = "ok"
        payload["lines"] = lines[-lines_requested:] if lines_requested else []
        if follow and as_json:
            payload["status"] = "unsupported"
            payload["error"] = "--json cannot be combined with --follow for monitor backend=file"
            return finish(2)
        if not follow:
            return finish(0)
        finish(0)
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(0, os.SEEK_END)
                while True:
                    line = fh.readline()
                    if line:
                        print(line.rstrip("\n"), flush=True)
                    else:
                        time.sleep(0.2)
        except KeyboardInterrupt:
            return 130
    if backend == "systemd":
        service = config.get("monitor", "service", fallback="").strip()
        payload["service"] = service
        if not service:
            payload["status"] = "unconfigured"
            payload["error"] = "monitor backend=systemd requires [monitor] service"
            return finish(2)
        if follow and as_json:
            payload["status"] = "unsupported"
            payload["error"] = "--json cannot be combined with --follow for monitor backend=systemd"
            return finish(2)
        journalctl = shutil.which("journalctl")
        if not journalctl:
            payload["status"] = "missing"
            payload["error"] = "journalctl is not available on this system"
            return finish(1)
        cmd = [journalctl, "-u", service, "-n", str(lines_requested), "--no-pager", "-o", "cat"]
        if follow:
            cmd.insert(5, "-f")
            payload["status"] = "ok"
            payload["command"] = ["journalctl", "-u", service, "-n", str(lines_requested), "-f", "--no-pager", "-o", "cat"]
            payload["lines"] = []
            finish(0)
            return subprocess.call(cmd)
        result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        payload["command"] = ["journalctl", "-u", service, "-n", str(lines_requested), "--no-pager", "-o", "cat"]
        payload["lines"] = result.stdout.splitlines()
        if result.returncode != 0:
            payload["status"] = "error"
            payload["error"] = result.stderr.strip() or f"journalctl exited {result.returncode}"
            return finish(result.returncode)
        payload["status"] = "ok"
        return finish(0)
    if backend in {"container", "docker", "command", "modelctl"}:
        payload["status"] = "not_implemented"
        payload["error"] = f"monitor backend '{backend}' is recognized but not implemented yet"
        return finish(2)
    payload["status"] = "unsupported"
    payload["error"] = f"unsupported monitor backend: {backend}"
    return finish(2)


def cmd_tail(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    port = str(getattr(args, "port", "")).strip()
    section = "monitor.ports"
    service = config.get(section, port, fallback="").strip()
    if not service:
        print(f"tail requires [{section}] {port} = <systemd-service>", file=sys.stderr)
        return 2
    derived = configparser.ConfigParser()
    for existing_section in config.sections():
        derived[existing_section] = dict(config.items(existing_section))
    if not derived.has_section("monitor"):
        derived.add_section("monitor")
    derived.set("monitor", "backend", "systemd")
    derived.set("monitor", "service", service)
    monitor_args = argparse.Namespace(target="router", follow=True, lines=getattr(args, "lines", 80), json=False)
    return cmd_monitor(monitor_args, derived)


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
    doctor = sub.add_parser(
        "doctor",
        help="Check configured paths and current capabilities",
        description="Check configured paths, writable state, and safety capabilities.",
        epilog=DOCTOR_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    doctor.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    list_cmd = sub.add_parser(
        "list",
        help="List detected models and aliases from configured router ini",
        description="List detected Models and Aliases from the configured router ini.",
        epilog=LIST_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    list_cmd.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    list_cmd.add_argument("--active", action="store_true", help="Show only active models")
    list_cmd.add_argument("--archived", action="store_true", help="Show only archived models")
    list_cmd.add_argument("--enabled", action="store_true", help="Show only enabled aliases")
    list_cmd.add_argument("--disabled", action="store_true", help="Show only disabled aliases")
    list_cmd.add_argument("target", nargs="?", help="Optional type (models/aliases/servers) or model/alias target")
    show = sub.add_parser(
        "show",
        help="Show details for a model or alias target",
        description="Show details for one model or alias target.",
        epilog=TARGET_HELP + "\nExamples:\n  modelctl show 1\n  modelctl show alias:my-model\n  modelctl show path:/models/model.gguf\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    show.add_argument("target", metavar="TARGET", help="Model or alias target; see formats below")
    show.add_argument("--gpu-vram-gib", type=float, help="Optional GPU VRAM size in GiB to estimate context and layer fit")
    show.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    aliases = sub.add_parser(
        "aliases",
        help="List aliases for a model target",
        description="List router aliases that point at a model target.",
        epilog=TARGET_HELP + "\nExamples:\n  modelctl aliases 1\n  modelctl aliases alias:my-model\n  modelctl aliases filename.gguf\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    aliases.add_argument("target", metavar="TARGET", help="Model target; e.g. 1, path:/models/model.gguf, or filename.gguf")
    aliases.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    delete = sub.add_parser(
        "delete",
        help="Interactively delete a model file and remove aliases; --dry-run to preview",
        description="Permanently deletes a model file and removes router aliases after interactive confirmation.",
        epilog=DELETE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    delete.add_argument("target", metavar="TARGET", help="Model target; e.g. 1, alias:my-model, path:/models/model.gguf, or filename.gguf")
    delete.add_argument("--dry-run", action="store_true", help="Preview file and alias removals without changing anything")
    delete.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    delete.add_argument("--apply", action="store_true", help="Explicitly apply destructive delete in non-interactive automation; writes recovery manifest first")
    archive = sub.add_parser(
        "archive",
        help="Archive model files while preserving aliases by default",
        description="Move model files to the archive tree; aliases are preserved unless --disable-aliases is used.",
        epilog=ARCHIVE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    archive.add_argument("target", nargs="*", metavar="TARGET", help="One or more model targets; e.g. 1 alias:my-model path:/models/model.gguf")
    archive.add_argument("--group", metavar="NAME", help="Archive a named group; currently supports: lab")
    archive.add_argument("--dry-run", action="store_true", help="Preview the archive plan without changing anything")
    archive.add_argument("--disable-aliases", action="store_true", help="Disable only aliases that directly point at archived models; default preserves aliases")
    archive.add_argument("--plan", metavar="PLAN.json", help="Optional path to write recovery metadata JSON")
    archive.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    update_check = sub.add_parser(
        "update-check",
        help="Check Hugging Face metadata for model updates",
        description="Check Hugging Face for a newer copy of a model file.",
        epilog=UPDATE_CHECK_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    update_check.add_argument("target", nargs="?", metavar="TARGET", help="Optional model target, e.g. 1 or alias:my-model")
    enable = sub.add_parser("enable", help="Enable an alias in the router ini", description="Enable a disabled alias in the router ini.", epilog=ENABLE_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    enable.add_argument("target", metavar="TARGET", help="Alias or model target, e.g. a2, qwen-mini, or model filename/stem")
    enable.add_argument("--dry-run", action="store_true", help="Preview ini edit without changing anything")
    disable = sub.add_parser("disable", help="Disable an alias in the router ini", description="Disable an alias in the router ini.", epilog=DISABLE_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    disable.add_argument("target", metavar="TARGET", help="Alias or model target, e.g. a2, qwen-mini, or model filename/stem")
    disable.add_argument("--dry-run", action="store_true", help="Preview ini edit without changing anything")
    add = sub.add_parser("add", help="Create an ini entry with estimated best defaults", description="Create a router ini entry with estimated best default flags/settings.", epilog=ADD_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    add.add_argument("--alias", required=True, help="Router alias/section name to create")
    add.add_argument("--model", required=True, help="GGUF model path for the new entry")
    add.add_argument("--dry-run", action="store_true", help="Preview entry without appending anything")
    add.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    add_entry = sub.add_parser("add-entry", help="Deprecated alias for add", description="Deprecated compatibility alias for `modelctl add`.", epilog=ADD_ENTRY_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_entry.add_argument("--alias", required=True, help="Router alias/section name to create")
    add_entry.add_argument("--model", required=True, help="GGUF model path for the new entry")
    add_entry.add_argument("--dry-run", action="store_true", help="Preview entry without appending anything")
    add_entry.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")

    benchmark = sub.add_parser("benchmark", help="Benchmark a model with llama.cpp and suggest settings", description="Benchmark a current model with llama.cpp and suggest the most appropriate settings.", epilog=BENCHMARK_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    benchmark.add_argument("target", metavar="TARGET", help="Model target, e.g. 1 or alias:my-model")
    benchmark.add_argument("--prompt-set", default="smoke", help="Prompt set to run; default: smoke")
    scan = sub.add_parser("scan", help="Scan for manually added GGUFs not yet in the ini", description="Scan the models folder for GGUF files not yet referenced by the router ini.", epilog=SCAN_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    scan.add_argument("--dry-run", action="store_true", help="Preview discovered entries without appending anything")
    restore = sub.add_parser("restore", help="Restore archived model files to active storage", description="Move archived model files back to active storage.", epilog=RESTORE_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    restore.add_argument("target", metavar="TARGET", help="Archived model target; e.g. 1, path:/archive/model.gguf, or filename.gguf")
    restore.add_argument("--dry-run", action="store_true", help="Preview restore without changing files or ini entries")
    restore.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    recover = sub.add_parser("recover", help="Recover aliases from a delete recovery manifest", description="Recover affected aliases/sections from focused delete recovery metadata.", epilog=RECOVER_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    recover.add_argument("manifest", metavar="MANIFEST.json", help="Delete recovery manifest JSON")
    recover.add_argument("--dry-run", action="store_true", help="Preview recovery without changing ini entries")
    recover.add_argument("--json", action="store_true", help="Emit stable JSON envelope output")
    monitor = sub.add_parser("monitor", help="Check local llama server status or recent logs", description="Check read-only local llama server status or recent logs without changing anything.", epilog=MONITOR_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    monitor.add_argument("target", nargs="?", default="router", metavar="TARGET", help="`discover`, `router`, or a local llama server port such as 8080")
    monitor.add_argument("--follow", action="store_true", help="Follow logs when supported")
    monitor.add_argument("--lines", type=int, default=80, help="Show N recent log lines when logs are available")
    monitor.add_argument("--json", action="store_true", help="Print machine-readable output")
    tail = sub.add_parser("tail", help="Follow configured logs for a local llama server port", description="Follow read-only configured logs for a local llama server port.", epilog=TAIL_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    tail.add_argument("port", metavar="PORT", help="Local llama server port mapped in [monitor.ports], e.g. 8080")
    tail.add_argument("--lines", type=int, default=80, help="Show N recent log lines before following")
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
    if args.command in {"add", "add-entry"}:
        return cmd_add_entry(args, config)
    if args.command == "benchmark":
        return cmd_benchmark(args, config)
    if args.command == "scan":
        return cmd_scan(args, config)
    if args.command == "restore":
        return cmd_restore(args, config)
    if args.command == "recover":
        return cmd_recover(args, config)
    if args.command == "monitor":
        return cmd_monitor(args, config)
    if args.command == "tail":
        return cmd_tail(args, config)
    if args.command == "rules":
        return cmd_rules(args, config)
    parser.error(f"Unhandled command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

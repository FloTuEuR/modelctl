#!/usr/bin/env python3
"""modelctl prototype: portable, safe-by-default llama.cpp router ini manager.

This framework intentionally implements only read/import/list/dry-run planning.
It does not edit router ini files or delete model files yet.
"""
from __future__ import annotations

import argparse
import configparser
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modelctl_core import (
    apply_archive_plan,
    augment_with_scanned_files,
    detect_from_ini,
    infer_archive_dirs,
    lab_model_paths,
    plan_archive_models,
    plan_delete_model,
    rollback_archive_plan,
)
import json


DEFAULT_CONFIG = Path.home() / ".config" / "modelctl" / "config.ini"


EXAMPLES = """
Examples:
  modelctl setup /path/to/models.ini                 # dry-run import preview
  modelctl setup /path/to/models.ini --yes           # write modelctl config/registry only
  modelctl doctor                                    # check configured setup
  modelctl list                                      # show models and aliases
  modelctl show model:1                              # show model details
  modelctl aliases model:1                           # show aliases for a model
  modelctl delete model:1                            # dry-run delete impact preview only
  modelctl archive model:1                           # dry-run archive impact preview
  modelctl archive model:1 --yes                     # move file, disable aliases, backup ini
  modelctl archive --group lab --yes                 # archive aliases under lab/testing section
  modelctl rollback /path/to/archive-plan.json --yes # restore files and ini from plan
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
            f"Or, non-interactively: modelctl setup /path/to/models.ini --config {path} --yes"
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
    wizard_mode = router_ini is None
    if wizard_mode:
        router_ini = _wizard_router_ini()
    if router_ini is None:
        print("setup needs a router ini path.", file=sys.stderr)
        print("Example: modelctl setup /path/to/models.ini", file=sys.stderr)
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

    should_write = args.yes
    if wizard_mode and not should_write:
        should_write = _yes_no_prompt("Write modelctl config/registry so modelctl is ready to use?", default=True)

    if not should_write:
        print("\nDry-run only. No files were written.")
        print("Next:")
        print("  modelctl setup --yes")
        return 0

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
    print("ID  LOC       STATE    SIZE       ALIASES  ACTION            PATH")
    for idx, model in enumerate(imported.get("models", []), start=1):
        location = str(model.get("location", "active")).upper()
        print(
            f"{idx:<3} {location:<9} {model['state']:<8} {_format_size(model.get('size_bytes')):<10} "
            f"{len(model.get('aliases', [])):<7} {model.get('action', 'ok'):<17} {model['path']}"
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


def _print_model_details(imported: dict[str, Any], model_path: str) -> None:
    model = next((m for m in imported.get("models", []) if m["path"] == model_path), None)
    print("Model")
    print(f"  path: {model_path}")
    if model:
        print(f"  state: {model['state']}")
        print(f"  location: {model.get('location', 'active')}")
        print(f"  action: {model.get('action', 'ok')}")
        print(f"  size: {_format_size(model.get('size_bytes'))}")
    aliases = [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]
    print(f"  aliases: {len(aliases)}")
    for alias in aliases:
        state = "enabled" if alias.get("enabled") else "disabled"
        print(f"    - {alias['section']} ({state})")


def cmd_show(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    model_path = _resolve_model_target(imported, args.target)
    if model_path:
        _print_model_details(imported, model_path)
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
    print("Safety: delete is dry-run only. Archive supports dry-run by default and requires --yes; it writes rollback metadata.")
    return exit_code


def cmd_delete(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    imported = _import_from_config(config)
    model_path = _resolve_model_target(imported, args.target)
    if model_path is None:
        print(f"Could not resolve model target: {args.target}", file=sys.stderr)
        print("Try: modelctl list", file=sys.stderr)
        return 2
    plan = plan_delete_model(imported, model_path)
    print("DRY RUN: delete model impact preview")
    print(f"  model: {plan['model_path']}")
    print(f"  aliases impacted: {len(plan['aliases_impacted'])}")
    for alias in plan["aliases_impacted"]:
        print(f"    - {alias}")
    print(f"  files that would be deleted: {len(plan['files_to_delete'])}")
    for path in plan["files_to_delete"]:
        print(f"    - {path}")
    for warning in plan["warnings"]:
        print(f"  warning: {warning}")
    print("No files or ini entries were changed. Mutating delete is not implemented in this safety framework yet.")
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
    if not args.yes:
        _print_archive_plan(plan, dry_run=True)
        print("No files or ini entries were changed. Re-run with --yes to apply this exact archive plan.")
        return 0
    plan_path = Path(args.plan).expanduser() if args.plan else _default_plan_path(args.config)
    try:
        applied = apply_archive_plan(plan, plan_path=plan_path)
    except Exception as exc:
        print(f"archive failed safely: {exc}", file=sys.stderr)
        return 1
    _print_archive_plan(applied, dry_run=False)
    print(f"  rollback plan: {plan_path}")
    print("Archive applied. Router ini backup and rollback metadata were written.")
    return 0


def cmd_rollback(args: argparse.Namespace, config: configparser.ConfigParser) -> int:
    plan_path = Path(args.plan).expanduser()
    if not plan_path.exists():
        print(f"rollback plan not found: {plan_path}", file=sys.stderr)
        return 2
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    print("DRY RUN: archive rollback preview")
    print(f"  router ini: {plan.get('router_ini')}")
    print(f"  files to restore: {len(plan.get('moved') or plan.get('entries') or [])}")
    if not args.yes:
        print("No files or ini entries were changed. Re-run with --yes to apply rollback.")
        return 0
    try:
        result = rollback_archive_plan(plan)
    except Exception as exc:
        print(f"rollback failed safely: {exc}", file=sys.stderr)
        return 1
    print(f"APPLIED: rollback restored {result['files']} file(s) and router ini {result['router_ini']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Portable safe-by-default llama.cpp router ini model manager",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to modelctl config.ini")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Import existing router ini and write minimal modelctl config/registry")
    setup.add_argument("ini_path", nargs="?", help="Path to llama.cpp router models ini/preset")
    setup.add_argument("--ini", required=False, help="Path to llama.cpp router models ini/preset")
    setup.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to write config.ini")
    setup.add_argument("--registry", help="Path to write modelctl.yaml registry")
    setup.add_argument("--yes", action="store_true", help="Actually write modelctl config/registry")

    sub.add_parser("import", help="Refresh registry from configured router ini without router changes")
    sub.add_parser("doctor", help="Check configured paths and current capabilities")
    sub.add_parser("list", help="List detected models and aliases from configured router ini")
    show = sub.add_parser("show", help="Show details for model:1, alias:name, path:/x/model.gguf, or filename")
    show.add_argument("target")
    aliases = sub.add_parser("aliases", help="List aliases for a model target")
    aliases.add_argument("target")
    delete = sub.add_parser("delete", help="Dry-run delete impact preview only")
    delete.add_argument("target", help="model target, e.g. model:1, path:/x/model.gguf, or filename")
    archive = sub.add_parser("archive", help="Dry-run/apply archive move with ini alias disable and rollback plan")
    archive.add_argument("target", nargs="*", help="one or more model targets, e.g. model:1 path:/x/model.gguf filename")
    archive.add_argument("--group", help="archive a named group; currently supports: lab")
    archive.add_argument("--yes", action="store_true", help="Apply the archive plan; default is dry-run only")
    archive.add_argument("--plan", help="Path to write rollback plan JSON when applying")
    rollback = sub.add_parser("rollback", help="Dry-run/apply archive rollback from a plan JSON")
    rollback.add_argument("plan", help="Path to archive rollback plan JSON")
    rollback.add_argument("--yes", action="store_true", help="Apply rollback; default is dry-run only")
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
    if args.command == "rollback":
        return cmd_rollback(args, config)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _strip_comment_prefix(line: str) -> tuple[bool, str]:
    stripped = line.lstrip()
    if stripped.startswith("#"):
        after_hash = stripped[1:]
        if after_hash.startswith(" "):
            after_hash = after_hash[1:]
        return True, after_hash.rstrip("\n")
    return False, line.rstrip("\n")


def _parse_section_header(content: str) -> str | None:
    text = content.strip()
    if text.startswith("[") and "]" in text:
        return text[1 : text.index("]")].strip()
    return None


def _parse_key_value(content: str) -> tuple[str, str] | None:
    text = content.strip()
    if not text or text.startswith(("#", ";", "[")) or "=" not in text:
        return None
    key, value = text.split("=", 1)
    return key.strip(), value.strip()


def model_action(model: dict[str, Any]) -> str:
    """Return a compact action/status label for list output."""
    if model.get("state") == "missing":
        return "restore/download"
    if model.get("location") == "archived":
        return "archived"
    if not model.get("aliases"):
        return "could archive"
    return "ok"


def detect_from_ini(router_ini: str | Path) -> dict[str, Any]:
    """Import aliases/models from any llama.cpp-router ini without writing to it.

    Alias detection is intentionally generic: any section containing a `model = ...`
    key is treated as an alias. Fully commented sections are imported as disabled
    aliases when they contain a commented `model = ...` line.
    """
    ini_path = Path(router_ini)
    lines = ini_path.read_text(encoding="utf-8").splitlines()

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_group: str | None = None
    pending_note: str | None = None

    for lineno, raw in enumerate(lines, start=1):
        commented, content = _strip_comment_prefix(raw)
        parsed = _parse_key_value(content)

        if commented and _parse_section_header(content) is None and parsed is None:
            heading = content.strip()
            if heading and not set(heading) <= {"#", "=", "-"}:
                if re.search(r"\b\d+\)", heading) or heading.isupper():
                    current_group = heading
                    pending_note = None
                else:
                    pending_note = heading

        section_name = _parse_section_header(content)
        if section_name:
            if current is not None:
                current["end_line"] = lineno - 1
            current = {
                "section": section_name,
                "enabled": not commented,
                "start_line": lineno,
                "end_line": len(lines),
                "model_line": None,
                "group": current_group,
                "note": pending_note,
                "params": {},
            }
            pending_note = None
            sections.append(current)
            continue

        if current is None:
            continue

        if parsed is None:
            continue
        key, value = parsed
        current["params"][key] = value
        if key == "model":
            current["model_line"] = lineno

    aliases: list[dict[str, Any]] = []
    model_paths: list[str] = []
    for section in sections:
        model_path = section["params"].get("model")
        if not model_path:
            continue
        alias = {
            "section": section["section"],
            "enabled": section["enabled"],
            "model_path": model_path,
            "params": dict(section["params"]),
            "start_line": section.get("start_line"),
            "end_line": section.get("end_line"),
            "model_line": section.get("model_line"),
            "group": section.get("group"),
            "note": section.get("note"),
        }
        aliases.append(alias)
        model_paths.append(model_path)

    parent_counts = Counter(str(Path(path).expanduser().parent) for path in model_paths)
    download_dir = parent_counts.most_common(1)[0][0] if parent_counts else None

    models = []
    for path in sorted(set(model_paths)):
        p = Path(path)
        model = {
            "path": path,
            "state": "present" if p.exists() else "missing",
            "size_bytes": p.stat().st_size if p.exists() else None,
            "aliases": [a["section"] for a in aliases if a["model_path"] == path],
            "location": "active",
        }
        model["action"] = model_action(model)
        models.append(model)

    return {
        "router_ini": str(ini_path),
        "download_dir": download_dir,
        "aliases": aliases,
        "models": models,
    }


def infer_archive_dirs(download_dir: str | None) -> list[str]:
    if not download_dir:
        return []
    archive = Path(download_dir).expanduser() / "archive"
    return [str(archive)] if archive.exists() and archive.is_dir() else []


def augment_with_scanned_files(
    imported: dict[str, Any],
    model_dirs: list[str] | None = None,
    archive_dirs: list[str] | None = None,
) -> dict[str, Any]:
    """Add unreferenced active and archived GGUFs to imported state without writing.

    Active model directories are scanned shallowly. Archive directories are scanned
    recursively because archives are commonly organized by provider/model folders.
    """
    model_dirs = model_dirs or []
    archive_dirs = archive_dirs or []
    models_by_path = {m["path"]: dict(m) for m in imported.get("models", [])}
    archive_roots = [Path(p).expanduser() for p in archive_dirs]

    def add_file(path: Path, location: str) -> None:
        key = str(path)
        if key in models_by_path:
            model = models_by_path[key]
            model["location"] = location if location == "archived" else model.get("location", "active")
            model["action"] = model_action(model)
            return
        if not path.exists() or not path.is_file():
            return
        model = {
            "path": key,
            "state": "present",
            "size_bytes": path.stat().st_size,
            "aliases": [],
            "location": location,
        }
        model["action"] = model_action(model)
        models_by_path[key] = model

    for directory in model_dirs:
        root = Path(directory).expanduser()
        if not root.exists() or not root.is_dir():
            continue
        for path in root.glob("*.gguf"):
            if any(_is_relative_to(path, archive_root) for archive_root in archive_roots):
                continue
            add_file(path, "active")

    for directory in archive_roots:
        if not directory.exists() or not directory.is_dir():
            continue
        for path in directory.rglob("*.gguf"):
            add_file(path, "archived")

    result = dict(imported)
    result["archive_dirs"] = [str(p) for p in archive_roots]
    result["models"] = sorted(models_by_path.values(), key=lambda m: (m.get("location") == "archived", m["path"]))
    return result


def plan_delete_model(imported: dict[str, Any], model_path: str) -> dict[str, Any]:
    """Return a deletion impact plan; does not write or delete anything."""
    aliases = [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]
    alias_names = [a["section"] for a in aliases]
    warnings: list[str] = []
    if len(alias_names) > 1:
        warnings.append(f"multiple aliases will be impacted: {', '.join(alias_names)}")
    elif alias_names:
        warnings.append(f"alias will be impacted: {alias_names[0]}")
    else:
        warnings.append("no aliases currently reference this model")

    return {
        "version": 1,
        "action": "delete_model",
        "router_ini": imported.get("router_ini"),
        "model_path": model_path,
        "aliases": aliases,
        "aliases_impacted": alias_names,
        "files_to_delete": [model_path] if Path(model_path).exists() else [],
        "requires_confirmation": True,
        "warnings": warnings,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text via temp file + fsync + replace to avoid partial ini/plan writes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _model_family_from_filename(filename: str) -> tuple[str, str]:
    """Infer a stable archive vendor/family folder from a loose GGUF filename."""
    stem = filename[:-5] if filename.lower().endswith(".gguf") else filename
    low = stem.lower()
    if "gemma" in low:
        vendor = "google"
    elif "qwen" in low:
        vendor = "qwen"
    elif "gpt-oss" in low or "openai" in low:
        vendor = "openai"
    elif "llama" in low:
        vendor = "meta"
    elif "mistral" in low or "mixtral" in low:
        vendor = "mistralai"
    else:
        vendor = "local"

    family = re.sub(r"-(?:UD-)?(?:Q\d(?:_\d)?|IQ\d_[A-Z]+|[A-Z]+Q\d)[A-Za-z0-9_]*$", "", stem, flags=re.IGNORECASE)
    family = re.sub(r"-GGUF$", "", family, flags=re.IGNORECASE)
    return vendor, family or stem


def archive_destination(imported: dict[str, Any], model_path: str) -> str:
    roots = imported.get("archive_dirs") or []
    if roots:
        archive_root = Path(roots[0]).expanduser()
    else:
        download_dir = imported.get("download_dir") or str(Path(model_path).expanduser().parent)
        archive_root = Path(download_dir).expanduser() / "archive"
    source = Path(model_path).expanduser()
    vendor, family = _model_family_from_filename(source.name)
    return str(archive_root / vendor / family / source.name)


def is_lab_alias(alias: dict[str, Any]) -> bool:
    section = str(alias.get("section") or "").lower()
    group = str(alias.get("group") or "").lower()
    note = str(alias.get("note") or "").lower()
    if any(marker in section for marker in ("lab", "test")):
        return True
    if any(marker in group for marker in ("lab", "testing", "openwebui", "others")):
        # Headings such as "OTHERS / OPENWEBUI / TESTING" are an explicit lab bucket.
        return True
    return any(marker in note for marker in ("lab", "testing", "openwebui", "experiment", "challenger"))


def lab_model_paths(imported: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for alias in imported.get("aliases", []):
        if is_lab_alias(alias) and alias.get("model_path") not in paths:
            paths.append(alias["model_path"])
    return paths


def plan_archive_models(imported: dict[str, Any], model_paths: list[str]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for model_path in model_paths:
        if model_path in seen:
            continue
        seen.add(model_path)
        source = Path(model_path).expanduser()
        aliases = [a for a in imported.get("aliases", []) if a.get("model_path") == model_path]
        destination = Path(archive_destination(imported, model_path)).expanduser()
        if not source.exists():
            warnings.append(f"source missing, cannot archive: {source}")
        if str(source) == str(destination):
            warnings.append(f"source is already at archive destination: {source}")
        if destination.exists():
            warnings.append(f"destination already exists: {destination}")
        entries.append(
            {
                "source": str(source),
                "destination": str(destination),
                "aliases": aliases,
                "aliases_impacted": [a["section"] for a in aliases],
                "source_exists": source.exists(),
                "destination_exists": destination.exists(),
                "size_bytes": source.stat().st_size if source.exists() else None,
            }
        )
    return {
        "version": 1,
        "action": "archive_models",
        "created_at": _utc_now(),
        "router_ini": imported["router_ini"],
        "aliases_policy": "disable",
        "requires_confirmation": True,
        "entries": entries,
        "warnings": warnings,
    }


def _commented_assignment(line: str, key: str, value: str) -> str:
    indent = line[: len(line) - len(line.lstrip())]
    return f"{indent}# {key} = {value}"


def _comment_line(line: str) -> str:
    if not line.strip() or line.lstrip().startswith("#"):
        return line
    indent = line[: len(line) - len(line.lstrip())]
    return f"{indent}# {line[len(indent):]}"


def _updated_ini_for_archive(original_text: str, plan: dict[str, Any]) -> str:
    lines = original_text.splitlines()
    replacements: dict[int, str] = {}
    comment_ranges: list[tuple[int, int]] = []
    model_line_to_dest: dict[int, str] = {}
    for entry in plan.get("entries", []):
        for alias in entry.get("aliases", []):
            start = alias.get("start_line")
            end = alias.get("end_line")
            model_line = alias.get("model_line")
            if start and end:
                comment_ranges.append((int(start), int(end)))
            if model_line:
                model_line_to_dest[int(model_line)] = entry["destination"]

    for start, end in comment_ranges:
        for lineno in range(start, end + 1):
            if 1 <= lineno <= len(lines):
                replacements[lineno] = _comment_line(lines[lineno - 1])
    for lineno, destination in model_line_to_dest.items():
        if 1 <= lineno <= len(lines):
            replacements[lineno] = _commented_assignment(lines[lineno - 1], "model", destination)
    return "\n".join(replacements.get(i, line) for i, line in enumerate(lines, start=1)) + "\n"


def _updated_ini_for_delete(original_text: str, plan: dict[str, Any]) -> str:
    """Remove complete alias sections for aliases impacted by a delete plan."""
    lines = original_text.splitlines()
    remove_lines: set[int] = set()
    for alias in plan.get("aliases", []):
        start = alias.get("start_line")
        end = alias.get("end_line")
        if start and end:
            remove_lines.update(range(int(start), int(end) + 1))
    kept = [line for lineno, line in enumerate(lines, start=1) if lineno not in remove_lines]
    collapsed: list[str] = []
    for line in kept:
        if line.strip() or (collapsed and collapsed[-1].strip()):
            collapsed.append(line)
    while collapsed and not collapsed[-1].strip():
        collapsed.pop()
    return "\n".join(collapsed) + ("\n" if collapsed else "")


def apply_delete_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Apply a confirmed delete plan: backup ini, remove aliases, delete files."""
    if plan.get("action") != "delete_model":
        raise ValueError("not a delete plan")
    router_ini_value = plan.get("router_ini")
    if not router_ini_value:
        raise ValueError("delete plan has no router_ini")
    router_ini = Path(router_ini_value).expanduser()
    original_text = router_ini.read_text(encoding="utf-8")
    applied = dict(plan)
    applied["applied_at"] = _utc_now()
    applied["original_ini_sha256"] = _sha256_text(original_text)
    backup_path = router_ini.with_suffix(router_ini.suffix + ".delete.bak")
    applied["router_ini_backup"] = str(backup_path)

    _atomic_write_text(backup_path, original_text)
    _atomic_write_text(router_ini, _updated_ini_for_delete(original_text, applied))
    deleted_files: list[str] = []
    try:
        for file_path in plan.get("files_to_delete", []):
            path = Path(file_path).expanduser()
            if path.exists():
                path.unlink()
                deleted_files.append(str(path))
        applied["deleted_files"] = deleted_files
        return applied
    except Exception:
        _atomic_write_text(router_ini, original_text)
        raise


def apply_archive_plan(plan: dict[str, Any], plan_path: str | Path | None = None) -> dict[str, Any]:
    """Apply an archive plan: backup ini, disable aliases, move files, write rollback metadata."""
    if plan.get("action") != "archive_models":
        raise ValueError("not an archive plan")
    errors = [w for w in plan.get("warnings", []) if w.startswith(("source missing", "source is already", "destination already"))]
    if errors:
        raise ValueError("archive plan is not safely applicable: " + "; ".join(errors))

    router_ini = Path(plan["router_ini"]).expanduser()
    original_text = router_ini.read_text(encoding="utf-8")
    applied = dict(plan)
    applied["applied_at"] = _utc_now()
    applied["original_ini_sha256"] = _sha256_text(original_text)
    backup_path = router_ini.with_suffix(router_ini.suffix + ".bak")
    applied["router_ini_backup"] = str(backup_path)

    _atomic_write_text(backup_path, original_text)
    _atomic_write_text(router_ini, _updated_ini_for_archive(original_text, applied))
    moved: list[dict[str, str]] = []
    try:
        for entry in applied.get("entries", []):
            source = Path(entry["source"])
            destination = Path(entry["destination"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append({"source": str(source), "destination": str(destination)})
        applied["moved"] = moved
        if plan_path is not None:
            path = Path(plan_path).expanduser()
            _atomic_write_text(path, json.dumps(applied, indent=2, sort_keys=True) + "\n")
        return applied
    except Exception:
        for item in reversed(moved):
            destination = Path(item["destination"])
            source = Path(item["source"])
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        _atomic_write_text(router_ini, original_text)
        raise


def rollback_archive_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("action") != "archive_models":
        raise ValueError("not an archive plan")
    router_ini = Path(plan["router_ini"]).expanduser()
    moved = plan.get("moved") or [
        {"source": entry["source"], "destination": entry["destination"]} for entry in plan.get("entries", [])
    ]
    for item in moved:
        destination = Path(item["destination"])
        source = Path(item["source"])
        if destination.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(destination), str(source))
    if "original_ini_text" in plan:
        _atomic_write_text(router_ini, plan["original_ini_text"])
    elif plan.get("router_ini_backup") and Path(plan["router_ini_backup"]).exists():
        backup_text = Path(plan["router_ini_backup"]).read_text(encoding="utf-8")
        expected_hash = plan.get("original_ini_sha256")
        if expected_hash and _sha256_text(backup_text) != expected_hash:
            raise ValueError("rollback ini backup hash mismatch")
        _atomic_write_text(router_ini, backup_text)
    else:
        raise ValueError("rollback plan has no ini backup/original text")
    return {"rolled_back": True, "router_ini": str(router_ini), "files": len(moved)}

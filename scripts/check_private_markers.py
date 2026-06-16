#!/usr/bin/env python3
"""Scan tracked text files for private/local markers.

This CI helper intentionally scans the publishable repository tree, not generated
caches or local runtime artifacts. It allows generic safety documentation to
mention concepts such as secrets or tokens, while still failing on concrete
private paths, hostnames, endpoints, or credential-looking assignments.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIR_PARTS = {
    ".git",
    ".runlogs",
    ".pytest_cache",
    ".venv",
    "venv",
    "__pycache__",
    "test_tmp",
    "private",
}

SKIP_FILES = {
    Path("tests/test_production_readiness.py"),
    Path("scripts/check_private_markers.py"),
}

TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

PRIVATE_MARKERS = [
    "/home/flori",
    "C:\\Users\\flori",
    "flori@",
    "localai",
    "buster",
    "Buster",
    "DESTROY",
    "AEGIS",
    "Virtue",
    "TrueNAS",
    "Merryfield",
    "42331",
    "/mnt/windows-ssd",
]

# Concrete private network locations are unsafe in public docs/code. Keep this
# narrower than all RFC1918 addresses so examples like 192.0.2.0/24 are fine.
PRIVATE_ENDPOINT_PATTERNS = [
    re.compile(r"https?://(?:192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[0-1])\.)[^\s)>'\"]+"),
]

# Credential-looking assignments/headers. Generic prose such as "do not commit
# secrets or tokens" is intentionally allowed.
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|bearer|authorization|x-api-key|github_token|hf_token|openai[_-]?api[_-]?key|anthropic[_-]?api[_-]?key)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
    re.compile(r"(?i)\bAuthorization\s*:\s*Bearer\s+[^\s'\"]{8,}"),
]


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    names = [name for name in result.stdout.decode("utf-8", errors="replace").split("\0") if name]
    return [ROOT / name for name in names]


def should_scan(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if rel in SKIP_FILES:
        return False
    if any(part in SKIP_DIR_PARTS for part in rel.parts):
        return False
    if path.suffix not in TEXT_SUFFIXES:
        return False
    return path.is_file()


def read_text(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return f"<<UNREADABLE: {exc}>>"
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_file(path: Path) -> list[str]:
    text = read_text(path)
    if text is None:
        return []
    rel = path.relative_to(ROOT)
    hits: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for marker in PRIVATE_MARKERS:
            if marker in line:
                hits.append(f"{rel}:{lineno}: contains private marker {marker!r}")
        for pattern in PRIVATE_ENDPOINT_PATTERNS:
            if pattern.search(line):
                hits.append(f"{rel}:{lineno}: contains private endpoint-like URL")
        for pattern in SECRET_PATTERNS:
            if pattern.search(line):
                hits.append(f"{rel}:{lineno}: contains credential-looking assignment/header")
    return hits


def main() -> int:
    hits: list[str] = []
    for path in tracked_files():
        if should_scan(path):
            hits.extend(scan_file(path))
    if hits:
        print("Private marker scan failed:", file=sys.stderr)
        print("\n".join(hits), file=sys.stderr)
        return 1
    print("Private marker scan passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

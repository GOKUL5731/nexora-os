#!/usr/bin/env python3
"""Rename NEXORA branding to NEXORA across the repository."""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "nexora_py310_venv",
    "nexora_py310_venv",
    ".cursor",
}

SKIP_SUFFIXES = {".db", ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf"}

# Apply longest-first to avoid partial replacements
TEXT_REPLACEMENTS = [
    ("nexora_os", "nexora_os"),
    ("NexoraRuntime", "NexoraRuntime"),
    ("NexoraProvider", "NexoraProvider"),
    ("NexoraContext", "NexoraContext"),
    ("useNexora", "useNexora"),
    ("nexoraApi", "nexoraApi"),
    ("NEXORA", "NEXORA"),
    ("Nexora", "Nexora"),
    ("nexora", "nexora"),
]

FILE_RENAMES = [
    ("nexora_os", "nexora_os"),
    ("NexoraContext.tsx", "NexoraContext.tsx"),
    ("start_nexora.py", "start_nexora.py"),
    ("start_nexora.bat", "start_nexora.bat"),
    ("start_nexora.sh", "start_nexora.sh"),
    ("NEXORA_ONE_CLICK.cmd", "NEXORA_ONE_CLICK.cmd"),
]


def should_process(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    if path.suffix.lower() in SKIP_SUFFIXES:
        return False
    if path.name.endswith(".min.js") or "node_modules" in path.as_posix():
        return False
    return True


def replace_in_file(path: Path) -> bool:
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    updated = raw
    for old, new in TEXT_REPLACEMENTS:
        updated = updated.replace(old, new)
    if updated != raw:
        path.write_text(updated, encoding="utf-8", newline="\n")
        return True
    return False


def rename_paths() -> None:
    # Rename files/dirs bottom-up
    all_paths = sorted(ROOT.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    for path in all_paths:
        name = path.name
        new_name = name
        for old, new in FILE_RENAMES:
            if old in new_name:
                new_name = new_name.replace(old, new)
        if new_name != name:
            target = path.with_name(new_name)
            if not target.exists():
                path.rename(target)


def main() -> None:
    # 1) content pass before directory rename (while nexora_os still exists)
    changed = 0
    for path in ROOT.rglob("*"):
        if path.is_file() and should_process(path):
            if replace_in_file(path):
                changed += 1
    print(f"Updated {changed} files")

    # 2) rename nexora_os directory and special files
    if (ROOT / "nexora_os").exists() and not (ROOT / "nexora_os").exists():
        (ROOT / "nexora_os").rename(ROOT / "nexora_os")
        print("Renamed nexora_os -> nexora_os")

    for old, new in FILE_RENAMES:
        if old == "nexora_os":
            continue
        for path in list(ROOT.rglob(f"*{old}*")):
            if path.is_file():
                new_name = path.name.replace(old, new)
                target = path.with_name(new_name)
                if target != path and not target.exists():
                    path.rename(target)

    # 3) second content pass for any missed references
    for path in ROOT.rglob("*"):
        if path.is_file() and should_process(path):
            replace_in_file(path)

    print("NEXORA rename complete.")


if __name__ == "__main__":
    main()

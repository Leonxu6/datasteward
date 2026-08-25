"""Shared primitives for DataSteward repository audits."""
from __future__ import annotations

import subprocess
from pathlib import Path

TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".txt", ".json", ".sh", ".sql", ".example"}
IGNORED_PARTS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", "build", "dist", "target", "dbt_packages"}


def require_root(root: object) -> Path:
    if not isinstance(root, Path):
        raise ValueError("root must be a pathlib.Path")
    if not root.exists() or not root.is_dir():
        raise ValueError("root must be an existing repository directory")
    return root


def relative_files(root: Path, *, suffixes: set[str] | None = None) -> list[Path]:
    root = require_root(root)
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in rel.parts):
            continue
        if suffixes is not None and path.suffix.lower() not in suffixes:
            continue
        files.append(rel)
    return sorted(files)


def _tracked_path(item: str) -> Path:
    path = Path(item)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("tracked file list contained a path outside repository")
    return path


def tracked_files(root: Path) -> list[Path]:
    root = require_root(root)
    try:
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True, timeout=10)
        text = result.stdout.decode("utf-8")
    except (FileNotFoundError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        raise ValueError("could not enumerate tracked repository files") from exc
    return [_tracked_path(item) for item in text.split("\0") if item]


def print_failures(failures: list[str]) -> int:
    for failure in failures:
        print(failure)
    return 1 if failures else 0

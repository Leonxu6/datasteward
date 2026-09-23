"""Shared primitives for DataSteward repository audits."""
from __future__ import annotations

import subprocess
from pathlib import Path

TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".txt", ".json", ".sh", ".sql", ".example"}
IGNORED_PARTS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", "build", "dist", "target", "dbt_packages"}
NON_RUNTIME_ROOTS = {"tests", "scripts"}
MAX_AUDITED_PYTHON_BYTES = 1_048_576
MAX_PRODUCTION_PYTHON_BYTES = MAX_AUDITED_PYTHON_BYTES


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


def tracked_python_files(root: Path) -> list[Path]:
    """Return bounded regular tracked Python files without following symlinks."""
    root = require_root(root)
    files: list[Path] = []
    for rel in tracked_files(root):
        if rel.suffix != ".py":
            continue
        path = root / rel
        if path.is_symlink() or not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ValueError(f"could not inspect tracked Python source: {rel}") from exc
        if size > MAX_AUDITED_PYTHON_BYTES:
            raise ValueError(
                f"tracked Python source exceeds {MAX_AUDITED_PYTHON_BYTES} byte audit limit: {rel}"
            )
        files.append(rel)
    return files


def production_python_files(root: Path) -> list[Path]:
    """Return bounded regular tracked runtime Python files without following symlinks."""
    return [
        rel
        for rel in tracked_python_files(root)
        if rel.parts and rel.parts[0] not in NON_RUNTIME_ROOTS
    ]


def print_failures(failures: list[str]) -> int:
    for failure in failures:
        print(failure)
    return 1 if failures else 0

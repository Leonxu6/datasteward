#!/usr/bin/env python3
"""Check repository-local Markdown links without making network requests."""
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def broken_local_links(root: Path) -> list[tuple[Path, str]]:
    broken: list[tuple[Path, str]] = []
    root_resolved = root.resolve()
    for source in sorted(root.rglob("*.md")):
        if source.is_symlink() or not source.is_file():
            continue
        text = source.read_text(encoding="utf-8")
        for raw_target in _LINK.findall(text):
            raw_target = raw_target.strip()
            if not raw_target:
                continue
            parsed = urlsplit(raw_target)
            if parsed.scheme or parsed.netloc:
                continue
            target = unquote(parsed.path)
            if not target:
                continue
            candidate = (root / target.lstrip("/")) if target.startswith("/") else (source.parent / target)
            try:
                resolved = candidate.resolve()
                inside_root = resolved.is_relative_to(root_resolved)
            except (OSError, RuntimeError):
                inside_root = False
                resolved = candidate
            if not inside_root or not resolved.exists():
                broken.append((source.relative_to(root), raw_target))
    return broken


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    broken = broken_local_links(root)
    for source, target in broken:
        print(f"{source}: broken local link -> {target}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())

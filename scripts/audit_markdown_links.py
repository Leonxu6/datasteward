#!/usr/bin/env python3
"""Check repository-local Markdown links without making network requests."""
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import unquote

_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def broken_local_links(root: Path) -> list[tuple[Path, str]]:
    broken: list[tuple[Path, str]] = []
    for source in sorted(root.rglob("*.md")):
        text = source.read_text(encoding="utf-8")
        for raw_target in _LINK.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            target = unquote(target)
            resolved = (root / target.lstrip("/")) if target.startswith("/") else (source.parent / target)
            if not resolved.resolve().exists():
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

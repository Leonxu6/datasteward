"""Defensive parsing helpers for dbt ``target/manifest.json`` files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator


def load_manifest(path: Path) -> dict | None:
    """Load a dbt manifest object or return ``None`` for missing/invalid documents."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def iter_nodes(manifest: dict, *, resource_type: str) -> Iterator[tuple[str, dict]]:
    """Yield well-formed nodes of one dbt resource type, ignoring corrupt entries."""
    nodes = manifest.get("nodes", {})
    if not isinstance(nodes, dict):
        return
    for unique_id, node in nodes.items():
        if not isinstance(unique_id, str) or not isinstance(node, dict):
            continue
        if node.get("resource_type") != resource_type:
            continue
        name = node.get("name")
        if not isinstance(name, str) or not name or name != name.strip():
            continue
        yield unique_id, node


def parent_names(manifest: dict, unique_id: str) -> list[str]:
    """Return stable de-duplicated dependency names for one node."""
    parent_map = manifest.get("parent_map", {})
    if not isinstance(parent_map, dict):
        return []
    parents = parent_map.get(unique_id, [])
    if not isinstance(parents, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for parent in parents:
        if not isinstance(parent, str) or not parent:
            continue
        name = parent.rsplit(".", 1)[-1]
        if name and name not in seen:
            result.append(name)
            seen.add(name)
    return result


def model_layer(node: dict) -> str:
    """Return a readable dbt layer name without trusting arbitrary FQN shapes."""
    fqn = node.get("fqn")
    if isinstance(fqn, list) and len(fqn) > 2 and isinstance(fqn[1], str) and fqn[1]:
        return fqn[1]
    return "dw"

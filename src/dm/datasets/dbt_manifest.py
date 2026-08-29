"""Defensive parsing helpers for dbt ``target/manifest.json`` files."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

_MAX_MANIFEST_BYTES = 64 * 1024 * 1024


def _manifest(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("manifest must be a JSON object")
    return value


def _clean_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty unpadded text")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field} contains control characters")
    return value


def load_manifest(path: Path) -> dict | None:
    """Load a bounded dbt manifest object or return ``None`` for invalid documents."""
    if not isinstance(path, (str, os.PathLike)):
        raise ValueError("manifest path must be a filesystem path")
    path = Path(path)
    try:
        metadata = path.stat()
        if metadata.st_size > _MAX_MANIFEST_BYTES:
            return None
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def iter_nodes(manifest: dict, *, resource_type: str) -> Iterator[tuple[str, dict]]:
    """Yield well-formed nodes of one dbt resource type, ignoring corrupt entries."""
    manifest = _manifest(manifest)
    resource_type = _clean_text(resource_type, field="resource_type")
    nodes = manifest.get("nodes", {})
    if not isinstance(nodes, dict):
        return
    for unique_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        try:
            unique_id = _clean_text(unique_id, field="dbt unique_id")
        except ValueError:
            continue
        if node.get("resource_type") != resource_type:
            continue
        try:
            _clean_text(node.get("name"), field="dbt node name")
        except ValueError:
            continue
        yield unique_id, node


def parent_names(manifest: dict, unique_id: str) -> list[str]:
    """Return stable de-duplicated dependency names for one node."""
    manifest = _manifest(manifest)
    unique_id = _clean_text(unique_id, field="unique_id")
    parent_map = manifest.get("parent_map", {})
    if not isinstance(parent_map, dict):
        return []
    parents = parent_map.get(unique_id, [])
    if not isinstance(parents, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for parent in parents:
        try:
            parent = _clean_text(parent, field="dbt parent unique_id")
            name = _clean_text(parent.rsplit(".", 1)[-1], field="dbt parent name")
        except ValueError:
            continue
        if name not in seen:
            result.append(name)
            seen.add(name)
    return result


def model_layer(node: dict) -> str:
    """Return a readable dbt layer name without trusting arbitrary FQN shapes."""
    if not isinstance(node, dict):
        raise ValueError("dbt node must be an object")
    fqn = node.get("fqn")
    if isinstance(fqn, list) and len(fqn) > 2 and isinstance(fqn[1], str):
        layer = fqn[1]
        if layer and layer == layer.strip() and not any(ord(ch) < 32 or ord(ch) == 127 for ch in layer):
            return layer
    return "dw"

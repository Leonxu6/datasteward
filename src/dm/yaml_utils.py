"""Strict YAML helpers for small trusted configuration files.

PyYAML's safe loader blocks arbitrary Python object construction, but it still
accepts duplicate mapping keys using last-write-wins semantics. Configuration
files should fail closed instead of silently changing meaning when a key is
repeated.
"""
from __future__ import annotations

from typing import Any

import yaml
from yaml.resolver import BaseResolver

_MAX_YAML_CHARS = 1_000_000


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects duplicate mapping keys."""


def _construct_unique_mapping(loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise ValueError("YAML mapping keys must be hashable") from exc
        if duplicate:
            raise ValueError(f"duplicate YAML mapping key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def safe_load_unique(text: object, *, max_chars: int = _MAX_YAML_CHARS) -> Any:
    """Safely parse bounded YAML text while rejecting duplicate mapping keys."""
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    if not isinstance(text, str):
        raise ValueError("YAML input must be text")
    if len(text) > max_chars:
        raise ValueError(f"YAML input must be at most {max_chars} characters")
    return yaml.load(text, Loader=_UniqueKeySafeLoader)

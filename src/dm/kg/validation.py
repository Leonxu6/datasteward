"""Validation helpers for user-controlled knowledge-graph queries."""
from __future__ import annotations

import operator
import re

_LABEL_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")


def bounded_int(value, *, name: str, minimum: int, maximum: int) -> int:
    """Return an integer in range without accepting bools or truncated floats."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}") from exc
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be an integer from {minimum} to {maximum}")
    return result


def required_text(value, *, name: str, max_length: int = 256) -> str:
    """Normalize required user text while rejecting padding and control characters."""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be non-empty and have no surrounding whitespace")
    if len(value) > max_length:
        raise ValueError(f"{name} must be at most {max_length} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{name} must not contain control characters")
    return value


def label_name(value: str, *, name: str = "target_type") -> str:
    """Validate a Cypher label before it is interpolated into a query."""
    value = required_text(value, name=name, max_length=64)
    if not _LABEL_RE.fullmatch(value):
        raise ValueError(f"{name} must be an ASCII Cypher label")
    return value

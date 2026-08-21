"""Validation helpers for the StarRocks compatibility adapter."""
from __future__ import annotations

import operator


def normalize_fetch_size(value) -> int:
    """Require a positive integer fetch batch size without bool/float coercion."""
    if isinstance(value, bool):
        raise ValueError("fetch size 必须是正整数，不能是布尔值")
    try:
        size = operator.index(value)
    except TypeError as exc:
        raise ValueError(f"fetch size 必须是正整数: {value!r}") from exc
    if size <= 0:
        raise ValueError(f"fetch size 必须大于 0: {size}")
    return size

"""Helpers for presenting backend failures without leaking raw exception details."""
from __future__ import annotations

import unicodedata

_MAX_OPERATION = 80


def safe_error_summary(operation: str, exc: BaseException) -> str:
    """Return a bounded, single-line operator message without exception text."""
    if not isinstance(operation, str):
        raise TypeError("operation must be text")
    operation = "".join(
        " " if unicodedata.category(ch) in {"Cc", "Cf", "Cs"} else ch
        for ch in operation
    )
    operation = " ".join(operation.split()).strip()
    if not operation:
        raise ValueError("operation must not be empty")
    if len(operation) > _MAX_OPERATION:
        operation = operation[:_MAX_OPERATION].rstrip()
    error_type = exc.__class__.__name__ if isinstance(exc, BaseException) else "Error"
    return f"{operation}失败（{error_type}）"

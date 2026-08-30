"""Serialize temporary ``sys.argv`` overrides used by embedded CLIs."""
from __future__ import annotations

import sys
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

_ARGV_LOCK = threading.RLock()
_MAX_ARGC = 64
_MAX_ARG = 4_096


def _validated_argv(argv: object) -> list[str]:
    if not isinstance(argv, Sequence) or isinstance(argv, (str, bytes, bytearray)):
        raise ValueError("argv must be a sequence of strings")
    if not argv:
        raise ValueError("argv must not be empty")
    if len(argv) > _MAX_ARGC:
        raise ValueError("argv contains too many arguments")
    validated: list[str] = []
    for item in argv:
        if not isinstance(item, str) or not item or len(item) > _MAX_ARG or "\x00" in item:
            raise ValueError("argv contains an invalid argument")
        validated.append(item)
    return validated


@contextmanager
def temporary_argv(argv: object) -> Iterator[None]:
    """Temporarily replace argv without leaking state across managed callers."""
    replacement = _validated_argv(argv)
    with _ARGV_LOCK:
        original = list(sys.argv)
        sys.argv[:] = replacement
        try:
            yield
        finally:
            sys.argv[:] = original

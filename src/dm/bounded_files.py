"""Descriptor-owned helpers for bounded local runtime artifacts."""
from __future__ import annotations

import os
import stat
from pathlib import Path

_READ_CHUNK_BYTES = 64 * 1024


def read_bounded_text(path: Path, *, max_bytes: int) -> str:
    """Read one regular file as UTF-8 without a path-based size-check race."""
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd = os.open(path, flags)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("artifact must be a regular file")
        if metadata.st_size > max_bytes:
            raise ValueError("artifact exceeds its size limit")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(fd, min(_READ_CHUNK_BYTES, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > max_bytes:
            raise ValueError("artifact exceeds its size limit")
        return payload.decode("utf-8")
    finally:
        os.close(fd)

"""Safe loading for document source files registered in metadata."""

import errno
import os
import stat
from pathlib import Path


MAX_DOCUMENT_SOURCE_BYTES = 1_048_576


def read_document_source(path: str | os.PathLike[str], *, max_bytes: int = MAX_DOCUMENT_SOURCE_BYTES) -> str:
    """Read one regular UTF-8 document without following symlinks or allocating unbounded memory."""
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise ValueError("max_bytes must be a positive integer")

    source = Path(path)
    if source.is_symlink():
        raise ValueError("document source must not be a symbolic link")

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError("document source must not be a symbolic link") from exc
        raise

    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("document source must be a regular file")
        if os.fstat(handle.fileno()).st_size > max_bytes:
            raise ValueError(f"document source exceeds the {max_bytes}-byte limit")
        payload = handle.read(max_bytes + 1)

    if len(payload) > max_bytes:
        raise ValueError(f"document source exceeds the {max_bytes}-byte limit")
    return payload.decode("utf-8")

"""Document metadata must not turn indexing into an unbounded or special-file read."""

import os

import pytest

from dm.docs.source import read_document_source


def test_reads_regular_utf8_document(tmp_path):
    source = tmp_path / "manual.md"
    source.write_text("设备维护说明", encoding="utf-8")

    assert read_document_source(source) == "设备维护说明"


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "10"])
def test_rejects_invalid_byte_limits(tmp_path, limit):
    source = tmp_path / "manual.md"
    source.write_text("text", encoding="utf-8")

    with pytest.raises(ValueError, match="positive integer"):
        read_document_source(source, max_bytes=limit)


def test_rejects_oversized_document_before_decoding(tmp_path):
    source = tmp_path / "manual.md"
    source.write_bytes(b"12345")

    with pytest.raises(ValueError, match="exceeds the 4-byte limit"):
        read_document_source(source, max_bytes=4)


def test_rejects_non_utf8_document(tmp_path):
    source = tmp_path / "manual.md"
    source.write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        read_document_source(source)


def test_rejects_directory_source(tmp_path):
    with pytest.raises((IsADirectoryError, ValueError)):
        read_document_source(tmp_path)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="platform has no FIFO support")
def test_rejects_fifo_without_waiting_for_a_writer(tmp_path):
    fifo = tmp_path / "document.pipe"
    os.mkfifo(fifo)

    with pytest.raises(ValueError, match="regular file"):
        read_document_source(fifo)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="platform has no symlink support")
def test_rejects_symbolic_link_source(tmp_path):
    target = tmp_path / "target.md"
    target.write_text("private data", encoding="utf-8")
    link = tmp_path / "source.md"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")

    with pytest.raises(ValueError, match="symbolic link"):
        read_document_source(link)

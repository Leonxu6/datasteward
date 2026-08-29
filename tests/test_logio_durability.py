import os

import pytest

from dm.warehouse import logio


def test_log_paths_reject_non_path_inputs():
    for value in (None, 7, object()):
        with pytest.raises(ValueError):
            logio.log_path(value, "audit")
        with pytest.raises(ValueError):
            logio.read_jsonl(value, "audit")


def test_encode_record_rejects_oversized_lines(monkeypatch):
    monkeypatch.setattr(logio, "_MAX_LINE_BYTES", 32)
    with pytest.raises(ValueError, match="exceeds"):
        logio.encode_record({"payload": "x" * 100})


def test_append_jsonl_fsyncs_after_complete_write(tmp_path, monkeypatch):
    calls = []
    real_fsync = os.fsync
    monkeypatch.setattr(logio.os, "fsync", lambda fd: calls.append(fd))
    logio.append_jsonl(tmp_path, "audit", {"id": 1})
    assert len(calls) == 1
    assert logio.read_jsonl(tmp_path, "audit") == [{"id": 1}]
    monkeypatch.setattr(logio.os, "fsync", real_fsync)


def test_read_jsonl_skips_oversized_corrupt_records_and_recovers(tmp_path, monkeypatch):
    monkeypatch.setattr(logio, "_MAX_LINE_BYTES", 32)
    path = logio.log_path(tmp_path, "audit")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'{"oversized":"' + b"x" * 80 + b'"}\n{"ok":1}\n')
    assert logio.read_jsonl(tmp_path, "audit") == [{"ok": 1}]


def test_read_jsonl_skips_invalid_utf8_without_losing_later_records(tmp_path):
    path = logio.log_path(tmp_path, "audit")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\n{\"ok\":2}\n")
    assert logio.read_jsonl(tmp_path, "audit") == [{"ok": 2}]

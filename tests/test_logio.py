from datetime import datetime

import pytest

from dm.warehouse.logio import append_jsonl, encode_record, log_path, normalize_log_name, read_jsonl


def test_log_name_rejects_path_traversal_and_ambiguous_names(tmp_path):
    assert normalize_log_name("audit_log") == "audit_log"
    for name in ("../audit", "a/b", "", ".hidden", "has space", "x" * 65, None):
        with pytest.raises(ValueError):
            normalize_log_name(name)
    assert log_path(tmp_path, "audit_log") == tmp_path / "audit_log.jsonl"


def test_encode_record_is_compact_utf8_json_with_one_newline():
    payload = encode_record({"user": "张三", "at": datetime(2026, 8, 21, 17, 0)})
    assert payload.endswith(b"\n")
    assert payload.count(b"\n") == 1
    assert "张三" in payload.decode("utf-8")
    assert "2026-08-21T17:00:00" in payload.decode("utf-8")


def test_encode_record_requires_mapping():
    with pytest.raises(TypeError):
        encode_record([1, 2])


def test_encode_record_rejects_non_finite_json_numbers():
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            encode_record({"metric": value})


def test_append_and_read_jsonl_round_trip(tmp_path):
    append_jsonl(tmp_path, "audit", {"id": 1})
    append_jsonl(tmp_path, "audit", {"id": 2})
    assert read_jsonl(tmp_path, "audit") == [{"id": 1}, {"id": 2}]


def test_read_jsonl_skips_corrupt_and_non_object_lines(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"ok":1}\n{bad\n[1,2]\n\n{"ok":2}\n', encoding="utf-8")
    assert read_jsonl(tmp_path, "audit") == [{"ok": 1}, {"ok": 2}]

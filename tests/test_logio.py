import os
import stat
from datetime import datetime, timezone

import pytest

from dm.warehouse import logio
from dm.warehouse.logio import append_jsonl, encode_record, log_path, normalize_log_name, read_jsonl


def test_utc_timestamp_is_timezone_aware_and_second_precision():
    value = logio.utc_timestamp()
    parsed = datetime.fromisoformat(value)

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
    assert parsed.microsecond == 0


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


def test_append_jsonl_retries_short_writes_until_record_is_complete(tmp_path, monkeypatch):
    original_write = logio.os.write
    calls = []

    def short_write(fd, payload):
        calls.append(len(payload))
        chunk = payload[: max(1, len(payload) // 2)]
        return original_write(fd, chunk)

    monkeypatch.setattr(logio.os, "write", short_write)
    append_jsonl(tmp_path, "audit", {"id": 7, "message": "完整记录"})

    assert len(calls) > 1
    assert read_jsonl(tmp_path, "audit") == [{"id": 7, "message": "完整记录"}]


@pytest.mark.skipif(not hasattr(os, "fchmod"), reason="platform has no descriptor chmod")
def test_append_jsonl_tightens_existing_file_permissions(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"id":1}\n', encoding="utf-8")
    path.chmod(0o666)

    append_jsonl(tmp_path, "audit", {"id": 2})

    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert read_jsonl(tmp_path, "audit") == [{"id": 1}, {"id": 2}]


@pytest.mark.skipif(
    not hasattr(os, "mkfifo") or not hasattr(os, "O_NONBLOCK"),
    reason="platform cannot create and reject FIFOs without blocking",
)
def test_append_jsonl_rejects_fifo_targets(tmp_path):
    path = tmp_path / "audit.jsonl"
    os.mkfifo(path)

    with pytest.raises(OSError):
        append_jsonl(tmp_path, "audit", {"id": 1})


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="platform has no O_NOFOLLOW")
def test_append_jsonl_rejects_symlink_targets(tmp_path):
    target = tmp_path / "real.jsonl"
    target.write_text('{"id":1}\n', encoding="utf-8")
    (tmp_path / "audit.jsonl").symlink_to(target)

    with pytest.raises(OSError):
        append_jsonl(tmp_path, "audit", {"id": 2})

    assert target.read_text(encoding="utf-8") == '{"id":1}\n'


@pytest.mark.skipif(
    not hasattr(os, "mkfifo") or not hasattr(os, "O_NONBLOCK"),
    reason="platform cannot create and reject FIFOs without blocking",
)
def test_read_jsonl_rejects_fifo_sources(tmp_path):
    os.mkfifo(tmp_path / "audit.jsonl")

    with pytest.raises(OSError, match="regular file"):
        read_jsonl(tmp_path, "audit")


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="platform has no O_NOFOLLOW")
def test_read_jsonl_rejects_symlink_sources(tmp_path):
    target = tmp_path / "real.jsonl"
    target.write_text('{"id":1}\n', encoding="utf-8")
    (tmp_path / "audit.jsonl").symlink_to(target)

    with pytest.raises(OSError):
        read_jsonl(tmp_path, "audit")


def test_read_jsonl_skips_corrupt_and_non_object_lines(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text('{"ok":1}\n{bad\n[1,2]\n\n{"ok":2}\n', encoding="utf-8")
    assert read_jsonl(tmp_path, "audit") == [{"ok": 1}, {"ok": 2}]


def test_read_jsonl_skips_nonstandard_constants_and_duplicate_keys(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_text(
        '{"ok":1}\n{"metric":NaN}\n{"id":1,"id":2}\n{"ok":2}\n',
        encoding="utf-8",
    )
    assert read_jsonl(tmp_path, "audit") == [{"ok": 1}, {"ok": 2}]

import json
from pathlib import Path

from scripts.audit_json_syntax import _MAX_JSON_BYTES, audit_file


def test_json_syntax_accepts_valid_json(tmp_path: Path):
    path = tmp_path / "ok.json"
    path.write_text(json.dumps({"ok": True}), encoding="utf-8")
    assert audit_file(path) == []


def test_json_syntax_reports_invalid_json(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text('{"ok":', encoding="utf-8")
    assert "invalid JSON" in audit_file(path)[0]


def test_json_syntax_rejects_nonstandard_constants(tmp_path: Path):
    for constant in ("NaN", "Infinity", "-Infinity"):
        path = tmp_path / "bad-number.json"
        path.write_text('{"value":' + constant + "}", encoding="utf-8")
        failures = audit_file(path)
        assert len(failures) == 1
        assert "invalid JSON" in failures[0]


def test_json_syntax_rejects_duplicate_object_keys(tmp_path: Path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"mode":"safe","mode":"unsafe"}', encoding="utf-8")
    failures = audit_file(path)
    assert len(failures) == 1
    assert "duplicate" in failures[0]


def test_json_syntax_rejects_symlinked_json(tmp_path: Path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"ok":true}', encoding="utf-8")
    link = tmp_path / "config.json"
    link.symlink_to(outside)

    failures = audit_file(link)

    assert len(failures) == 1
    assert "symbolic links" in failures[0]


def test_json_syntax_rejects_directory_named_json(tmp_path: Path):
    path = tmp_path / "config.json"
    path.mkdir()

    failures = audit_file(path)

    assert len(failures) == 1
    assert "regular file" in failures[0]


def test_json_syntax_rejects_oversized_files_before_parsing(tmp_path: Path):
    path = tmp_path / "oversized.json"
    path.write_bytes(b" " * (_MAX_JSON_BYTES + 1))

    failures = audit_file(path)

    assert len(failures) == 1
    assert "audit limit" in failures[0]

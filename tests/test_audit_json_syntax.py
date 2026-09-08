import json
from pathlib import Path

from scripts.audit_json_syntax import audit_file


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

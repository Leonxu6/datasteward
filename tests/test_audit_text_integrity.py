from pathlib import Path

from scripts.audit_text_integrity import audit_paths


def test_text_integrity_accepts_clean_utf8(tmp_path: Path):
    rel = Path("README.md")
    (tmp_path / rel).write_text("hello 世界\n", encoding="utf-8")
    assert audit_paths(tmp_path, [rel]) == []


def test_text_integrity_reports_bom_and_missing_newline(tmp_path: Path):
    bom = Path("bom.md")
    tail = Path("tail.py")
    (tmp_path / bom).write_bytes(b"\xef\xbb\xbfhello\n")
    (tmp_path / tail).write_text("x = 1", encoding="utf-8")
    failures = audit_paths(tmp_path, [bom, tail])
    assert any("BOM" in item for item in failures)
    assert any("final newline" in item for item in failures)

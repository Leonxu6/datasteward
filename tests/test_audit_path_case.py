from pathlib import Path

from scripts.audit_path_case import audit_paths


def test_path_case_audit_detects_collisions():
    assert audit_paths([Path("docs/Guide.md"), Path("docs/guide.md")]) == ["case-insensitive path collision: docs/Guide.md <-> docs/guide.md"]


def test_path_case_audit_accepts_distinct_paths():
    assert audit_paths([Path("docs/guide.md"), Path("tests/test_guide.py")]) == []

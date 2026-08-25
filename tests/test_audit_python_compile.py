from pathlib import Path

from scripts.audit_python_compile import audit_paths


def test_python_compile_audit_detects_syntax_errors(tmp_path: Path):
    good = Path("good.py")
    bad = Path("bad.py")
    (tmp_path / good).write_text("value = 1\n", encoding="utf-8")
    (tmp_path / bad).write_text("if True print('x')\n", encoding="utf-8")
    failures = audit_paths(tmp_path, [good, bad])
    assert len(failures) == 1
    assert failures[0].startswith("bad.py:")


def test_python_compile_audit_ignores_non_python_files(tmp_path: Path):
    rel = Path("notes.md")
    (tmp_path / rel).write_text("not python\n", encoding="utf-8")
    assert audit_paths(tmp_path, [rel]) == []

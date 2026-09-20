from pathlib import Path

from scripts.audit_toml_syntax import _MAX_TOML_BYTES, audit_file


def test_toml_syntax_accepts_valid_toml(tmp_path: Path):
    path = tmp_path / "ok.toml"
    path.write_text('[project]\nname="demo"\n', encoding="utf-8")
    assert audit_file(path) == []


def test_toml_syntax_reports_invalid_toml(tmp_path: Path):
    path = tmp_path / "bad.toml"
    path.write_text('[project\n', encoding="utf-8")
    assert "invalid TOML" in audit_file(path)[0]


def test_toml_syntax_rejects_symlinked_toml(tmp_path: Path):
    outside = tmp_path / "outside.toml"
    outside.write_text('[project]\nname="demo"\n', encoding="utf-8")
    link = tmp_path / "pyproject.toml"
    link.symlink_to(outside)

    failures = audit_file(link)

    assert len(failures) == 1
    assert "symbolic links" in failures[0]


def test_toml_syntax_rejects_directory_named_toml(tmp_path: Path):
    path = tmp_path / "pyproject.toml"
    path.mkdir()

    failures = audit_file(path)

    assert len(failures) == 1
    assert "regular file" in failures[0]


def test_toml_syntax_rejects_oversized_files_before_parsing(tmp_path: Path):
    path = tmp_path / "oversized.toml"
    path.write_bytes(b"#" * (_MAX_TOML_BYTES + 1))

    failures = audit_file(path)

    assert len(failures) == 1
    assert "audit limit" in failures[0]

from pathlib import Path

from scripts.audit_yaml_syntax import _MAX_YAML_BYTES, audit_file


def test_yaml_syntax_accepts_valid_yaml(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("service:\n  host: localhost\n  ports: [80, 443]\n", encoding="utf-8")
    assert audit_file(path) == []


def test_yaml_syntax_rejects_duplicate_keys(tmp_path: Path):
    path = tmp_path / "config.yml"
    path.write_text("service:\n  host: first\n  host: second\n", encoding="utf-8")
    failures = audit_file(path)
    assert failures
    assert "duplicate key" in failures[0]


def test_yaml_syntax_rejects_unsafe_python_tags(tmp_path: Path):
    path = tmp_path / "unsafe.yaml"
    path.write_text("value: !!python/object/apply:os.system ['echo unsafe']\n", encoding="utf-8")
    failures = audit_file(path)
    assert failures
    assert "invalid YAML" in failures[0]


def test_yaml_syntax_rejects_symlink_inputs(tmp_path: Path):
    target = tmp_path / "target.yaml"
    target.write_text("ok: true\n", encoding="utf-8")
    link = tmp_path / "link.yaml"
    link.symlink_to(target)
    assert "symbolic links are not accepted" in audit_file(link)[0]


def test_yaml_syntax_rejects_oversized_files_before_parsing(tmp_path: Path):
    path = tmp_path / "large.yaml"
    path.write_bytes(b"a" * (_MAX_YAML_BYTES + 1))
    assert "file exceeds" in audit_file(path)[0]

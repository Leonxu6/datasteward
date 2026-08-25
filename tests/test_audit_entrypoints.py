from pathlib import Path

import scripts.audit_entrypoints as audit_module


def _write_project(root: Path, target: str) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname="datasteward"\n[project.scripts]\ndm-app="' + target + '"\n',
        encoding="utf-8",
    )


def test_entrypoint_audit_accepts_existing_top_level_callable(tmp_path: Path):
    module = tmp_path / "src" / "dm" / "app.py"
    module.parent.mkdir(parents=True)
    module.write_text("def main():\n    return 0\n", encoding="utf-8")
    _write_project(tmp_path, "dm.app:main")

    assert audit_module.audit(tmp_path) == []


def test_entrypoint_audit_reports_missing_module_and_callable(tmp_path: Path):
    _write_project(tmp_path, "dm.missing:main")
    failures = audit_module.audit(tmp_path)
    assert len(failures) == 1
    assert "entrypoint module is missing" in failures[0]

    module = tmp_path / "src" / "dm" / "missing.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("VALUE = 1\n", encoding="utf-8")
    failures = audit_module.audit(tmp_path)
    assert len(failures) == 1
    assert "top-level callable main is missing" in failures[0]


def test_entrypoint_audit_rejects_invalid_target_syntax(tmp_path: Path):
    _write_project(tmp_path, "dm.app")
    assert audit_module.audit(tmp_path) == ["dm-app: entrypoint must use module:function syntax"]

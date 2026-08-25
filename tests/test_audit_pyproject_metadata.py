from pathlib import Path

import scripts.audit_pyproject_metadata as audit_module


def test_pyproject_metadata_accepts_required_contract(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit_module, "_REQUIRED_SCRIPTS", {"dm-app"})
    (tmp_path / "pyproject.toml").write_text('[project]\nname="datasteward"\nlicense={text="Apache-2.0"}\nrequires-python=">=3.10"\n[project.scripts]\ndm-app="dm.app:main"\n', encoding="utf-8")
    assert audit_module.audit(tmp_path) == []


def test_pyproject_metadata_reports_missing_entrypoint(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit_module, "_REQUIRED_SCRIPTS", {"dm-app"})
    (tmp_path / "pyproject.toml").write_text('[project]\nname="datasteward"\nlicense={text="Apache-2.0"}\nrequires-python=">=3.10"\n[project.scripts]\n', encoding="utf-8")
    assert audit_module.audit(tmp_path) == ["pyproject.toml: missing CLI entrypoint dm-app"]

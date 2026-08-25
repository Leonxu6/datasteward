from pathlib import Path

import scripts.audit_gitignore_contract as audit_module


def test_gitignore_contract_reports_missing_rules(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit_module, "_REQUIRED", {".env", "data/"})
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    assert audit_module.audit(tmp_path) == [".gitignore: missing required rule data/"]


def test_gitignore_contract_ignores_comments(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit_module, "_REQUIRED", {".env"})
    (tmp_path / ".gitignore").write_text("# secrets\n.env\n", encoding="utf-8")
    assert audit_module.audit(tmp_path) == []

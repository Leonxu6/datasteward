from pathlib import Path

import scripts.audit_docs_contract as audit_module


def test_docs_contract_reports_missing_docs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit_module, "_REQUIRED", {"README.md": 5, "docs/ops.md": 5})
    (tmp_path / "README.md").write_text("enough\n", encoding="utf-8")
    assert audit_module.audit(tmp_path) == ["docs/ops.md: required maintainer documentation is missing"]


def test_docs_contract_reports_small_docs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(audit_module, "_REQUIRED", {"README.md": 20})
    (tmp_path / "README.md").write_text("tiny\n", encoding="utf-8")
    assert "unexpectedly small" in audit_module.audit(tmp_path)[0]

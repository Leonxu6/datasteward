from pathlib import Path

from scripts.audit_workflow_security import audit


def _workflow(root: Path, text: str):
    directory = root / ".github" / "workflows"
    directory.mkdir(parents=True)
    (directory / "ci.yml").write_text(text, encoding="utf-8")


def test_workflow_security_accepts_read_only_versioned_actions(tmp_path: Path):
    _workflow(tmp_path, "permissions:\n  contents: read\njobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n")
    assert audit(tmp_path) == []


def test_workflow_security_rejects_moving_refs_and_missing_permissions(tmp_path: Path):
    _workflow(tmp_path, "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@main\n")
    failures = audit(tmp_path)
    assert any("permissions contents: read" in item for item in failures)
    assert any("stable version" in item for item in failures)

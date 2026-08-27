from pathlib import Path

import scripts.audit_common as audit_common


def test_production_python_files_excludes_tests_and_audit_tooling(monkeypatch, tmp_path):
    monkeypatch.setattr(
        audit_common,
        "tracked_files",
        lambda root: [
            Path("src/datasteward/config.py"),
            Path("src/datasteward/health/checks.py"),
            Path("tests/test_config.py"),
            Path("scripts/audit_common.py"),
            Path("README.md"),
        ],
    )

    assert audit_common.production_python_files(tmp_path) == [
        Path("src/datasteward/config.py"),
        Path("src/datasteward/health/checks.py"),
    ]

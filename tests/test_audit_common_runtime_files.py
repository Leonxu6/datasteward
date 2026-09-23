from pathlib import Path

import pytest

import scripts.audit_common as audit_common


def test_production_python_files_excludes_tests_and_audit_tooling(monkeypatch, tmp_path):
    (tmp_path / "src" / "datasteward" / "health").mkdir(parents=True)
    (tmp_path / "src" / "datasteward" / "config.py").write_text("CONFIG = True\n", encoding="utf-8")
    (tmp_path / "src" / "datasteward" / "health" / "checks.py").write_text("CHECKS = True\n", encoding="utf-8")
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


def test_production_python_files_skips_symlinks_and_non_files(monkeypatch, tmp_path):
    package = tmp_path / "src" / "datasteward"
    package.mkdir(parents=True)
    (package / "runtime.py").write_text("RUNTIME = True\n", encoding="utf-8")
    outside = tmp_path.parent / "outside-runtime.py"
    outside.write_text("OUTSIDE = True\n", encoding="utf-8")
    linked = package / "linked.py"
    try:
        linked.symlink_to(outside)
    except OSError:
        pytest.skip("filesystem does not permit symlink creation")
    (package / "directory.py").mkdir()

    monkeypatch.setattr(
        audit_common,
        "tracked_files",
        lambda root: [
            Path("src/datasteward/runtime.py"),
            Path("src/datasteward/linked.py"),
            Path("src/datasteward/directory.py"),
            Path("src/datasteward/missing.py"),
        ],
    )

    assert audit_common.production_python_files(tmp_path) == [Path("src/datasteward/runtime.py")]


def test_production_python_files_rejects_oversized_runtime_source(monkeypatch, tmp_path):
    package = tmp_path / "src" / "datasteward"
    package.mkdir(parents=True)
    oversized = package / "runtime.py"
    oversized.write_bytes(b"x" * (audit_common.MAX_PRODUCTION_PYTHON_BYTES + 1))
    monkeypatch.setattr(
        audit_common,
        "tracked_files",
        lambda root: [Path("src/datasteward/runtime.py")],
    )

    with pytest.raises(ValueError, match="exceeds .* audit limit"):
        audit_common.production_python_files(tmp_path)

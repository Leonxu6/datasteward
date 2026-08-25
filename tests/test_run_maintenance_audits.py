from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import scripts.run_maintenance_audits as runner


def test_runner_executes_requested_audits_and_collects_failures(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    for name in ("ok.py", "bad.py"):
        (scripts_dir / name).write_text("# audit fixture\n", encoding="utf-8")

    results = [
        SimpleNamespace(returncode=0, stdout="", stderr=""),
        SimpleNamespace(returncode=1, stdout="broken contract\n", stderr=""),
    ]
    with patch.object(runner.subprocess, "run", side_effect=results) as run:
        failures = runner.run_audits(tmp_path, scripts=("ok.py", "bad.py"))

    assert failures == ["bad.py: broken contract"]
    assert run.call_count == 2


def test_runner_reports_missing_and_timed_out_audits(tmp_path: Path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "slow.py").write_text("# audit fixture\n", encoding="utf-8")

    with patch.object(runner.subprocess, "run", side_effect=runner.subprocess.TimeoutExpired("audit", 30)):
        failures = runner.run_audits(tmp_path, scripts=("missing.py", "slow.py"))

    assert failures == ["missing.py: audit script is missing", "slow.py: audit timed out"]


def test_runner_rejects_non_directory_roots(tmp_path: Path):
    with pytest.raises(ValueError, match="existing directory"):
        runner.run_audits(tmp_path / "missing", scripts=())


@pytest.mark.parametrize(
    "scripts",
    [
        ("../outside.py",),
        ("nested/audit.py",),
        ("nested\\audit.py",),
        (" padded.py",),
        ("audit.txt",),
        ("same.py", "same.py"),
    ],
)
def test_runner_rejects_unsafe_or_duplicate_script_selectors(tmp_path: Path, scripts: tuple[str, ...]):
    (tmp_path / "scripts").mkdir()
    with pytest.raises(ValueError, match="audit script names"):
        runner.run_audits(tmp_path, scripts=scripts)

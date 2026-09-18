import os
import subprocess
import sys
from pathlib import Path


def test_default_data_directory_is_project_data_not_process_cwd(tmp_path):
    env = os.environ.copy()
    env.pop("DM_DATA_DIR", None)
    code = "from dm.config import DATA_DIR, PROJECT_ROOT; print(DATA_DIR); print(PROJECT_ROOT)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    data_dir_text, project_root_text = result.stdout.strip().splitlines()
    project_root = Path(project_root_text)
    assert Path(data_dir_text) == project_root / "data"
    assert Path(data_dir_text) != tmp_path


def test_explicit_relative_data_directory_remains_cwd_relative(tmp_path):
    env = os.environ.copy()
    env["DM_DATA_DIR"] = "custom-data"
    result = subprocess.run(
        [sys.executable, "-c", "from dm.config import DATA_DIR; print(DATA_DIR)"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert Path(result.stdout.strip()) == (tmp_path / "custom-data").resolve()

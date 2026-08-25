from pathlib import Path

import pytest

from scripts.audit_common import relative_files


def test_relative_files_skips_symlinks_that_can_escape_repository(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "inside.txt").write_text("inside\n", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    link = root / "outside-link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("filesystem does not permit symlink creation")

    assert relative_files(root, suffixes={".txt"}) == [Path("inside.txt")]

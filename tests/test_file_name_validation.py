"""Dataset and cursor name validation for FileConnector."""

from pathlib import Path

import pytest

from dm.connect.base import Source
from dm.connect.file import FileConnector


def _connector(path: Path) -> FileConnector:
    return FileConnector(
        Source(name="files", source_type="file", params={"dir": str(path)})
    )


@pytest.mark.parametrize("name", ["orders\x00csv", "orders\tdata", "orders\ndata", "orders\rdata", "orders\x7fdata"])
def test_file_dataset_name_rejects_control_characters(tmp_path: Path, name: str):
    (tmp_path / "orders.csv").write_text("id\n1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="控制字符"):
        _connector(tmp_path).read_table(name)

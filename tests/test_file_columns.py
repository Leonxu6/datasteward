"""Column normalization behavior for FileConnector."""

from pathlib import Path

import pandas as pd
import pytest

from dm.connect.base import Source
from dm.connect.file import FileConnector


def _connector(path: Path) -> FileConnector:
    return FileConnector(
        Source(name="files", source_type="file", params={"dir": str(path)})
    )


def test_file_read_normalizes_non_string_column_labels(tmp_path: Path, monkeypatch):
    (tmp_path / "orders.csv").write_text("placeholder\n1\n", encoding="utf-8")
    connector = _connector(tmp_path)
    monkeypatch.setattr(
        connector,
        "_read_df",
        lambda path, nrows=None: pd.DataFrame([[1, "open"]], columns=[101, "status"]),
    )

    columns, rows = connector.read_table("orders")

    assert columns == ["101", "status"]
    assert rows == [(1, "open")]


def test_file_incremental_cursor_uses_normalized_column_labels(tmp_path: Path, monkeypatch):
    (tmp_path / "orders.csv").write_text("placeholder\n1\n", encoding="utf-8")
    connector = _connector(tmp_path)
    monkeypatch.setattr(
        connector,
        "_read_df",
        lambda path, nrows=None: pd.DataFrame([[1, 10], [2, 20]], columns=["id", 2026]),
    )

    columns, rows = connector.read_table("orders", cursor_col="2026", since=10)

    assert columns == ["id", "2026"]
    assert rows == [(2, 20)]


def test_file_columns_reject_stringification_collisions(tmp_path: Path, monkeypatch):
    (tmp_path / "orders.csv").write_text("placeholder\n1\n", encoding="utf-8")
    connector = _connector(tmp_path)
    monkeypatch.setattr(
        connector,
        "_read_df",
        lambda path, nrows=None: pd.DataFrame([[1, 2]], columns=[1, "1"]),
    )

    with pytest.raises(ValueError, match="字符串化后存在重复"):
        connector.read_table("orders")

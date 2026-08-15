"""FileConnector 的纯单元测试：目录校验、文件解析、类型归一与增量读取边界。"""

from pathlib import Path

import pandas as pd
import pytest

from dm.connect.base import Source
from dm.connect.file import FileConnector, _dtype_to_base


def _connector(path: Path) -> FileConnector:
    return FileConnector(
        Source(name="test_files", source_type="file", params={"dir": str(path)})
    )


@pytest.mark.parametrize(
    ("dtype", "expected"),
    [
        ("int64", "integer"),
        ("Int64", "integer"),
        ("uint32", "integer"),
        ("Float64", "double"),
        ("bool", "boolean"),
        ("boolean", "boolean"),
        ("datetime64[ns]", "timestamp"),
        ("object", "varchar"),
    ],
)
def test_dtype_to_base_handles_numpy_and_nullable_pandas_dtypes(dtype, expected):
    assert _dtype_to_base(dtype) == expected


def test_connection_rejects_regular_file(tmp_path):
    source_path = tmp_path / "not-a-directory"
    source_path.write_text("data", encoding="utf-8")

    ok, message = _connector(source_path).test_connection()

    assert ok is False
    assert "不是目录" in message


def test_read_table_rejects_path_traversal(tmp_path):
    (tmp_path / "orders.csv").write_text("id\n1\n", encoding="utf-8")
    connector = _connector(tmp_path)

    with pytest.raises(ValueError, match="当前目录"):
        connector.read_table("../orders")


@pytest.mark.parametrize("requested_name", ["orders", "Orders.CSV"])
def test_read_table_resolves_case_insensitive_csv_names(tmp_path, requested_name):
    (tmp_path / "Orders.CSV").write_text("id,name\n1,alpha\n2,beta\n", encoding="utf-8")
    connector = _connector(tmp_path)

    columns, rows = connector.read_table(requested_name, limit=1)

    assert columns == ["id", "name"]
    assert rows == [(1, "alpha")]


def test_duplicate_stem_keeps_csv_priority(tmp_path):
    (tmp_path / "orders.csv").write_text("id\n7\n", encoding="utf-8")
    # 无需安装 Excel 依赖：只要解析优先级正确，就不会尝试读取这个占位 xlsx。
    (tmp_path / "orders.xlsx").write_text("not a real workbook", encoding="utf-8")
    connector = _connector(tmp_path)

    columns, rows = connector.read_table("orders")

    assert columns == ["id"]
    assert rows == [(7,)]


def test_introspect_deduplicates_same_logical_stem(tmp_path):
    """目录里 CSV/XLSX 同 stem 时，catalog 只能暴露 read_table 实际会读取的那个数据集。"""
    (tmp_path / "orders.csv").write_text("id,name\n7,alpha\n", encoding="utf-8")
    # 若 introspect 没有去重，会尝试解析这个无效 xlsx；去重后 CSV 优先且只暴露一次 orders。
    (tmp_path / "orders.xlsx").write_text("not a real workbook", encoding="utf-8")
    (tmp_path / "customers.csv").write_text("id\n9\n", encoding="utf-8")
    connector = _connector(tmp_path)

    datasets = connector.introspect()

    assert [dataset.name for dataset in datasets] == ["customers", "orders"]
    orders = next(dataset for dataset in datasets if dataset.name == "orders")
    assert orders.col_names() == ["id", "name"]


def test_introspect_ignores_directories_named_like_supported_files(tmp_path):
    (tmp_path / "nested.csv").mkdir()
    (tmp_path / "actual.csv").write_text("id,active\n1,true\n", encoding="utf-8")
    connector = _connector(tmp_path)

    datasets = connector.introspect()

    assert [dataset.name for dataset in datasets] == ["actual"]
    assert datasets[0].col_names() == ["id", "active"]


def test_zero_limit_returns_no_rows(tmp_path):
    (tmp_path / "orders.csv").write_text("id\n1\n2\n", encoding="utf-8")
    connector = _connector(tmp_path)

    columns, rows = connector.read_table("orders", limit=0)

    assert columns == ["id"]
    assert rows == []


def test_snapshot_limit_is_pushed_down_to_reader(tmp_path, monkeypatch):
    (tmp_path / "orders.csv").write_text("id\n1\n2\n3\n", encoding="utf-8")
    connector = _connector(tmp_path)
    calls = []

    def fake_read(path, nrows=None):
        calls.append(nrows)
        df = pd.DataFrame({"id": [1, 2, 3]})
        return df.head(nrows) if nrows is not None else df

    monkeypatch.setattr(connector, "_read_df", fake_read)

    columns, rows = connector.read_table("orders", limit=2)

    assert calls == [2]
    assert columns == ["id"]
    assert rows == [(1,), (2,)]


def test_incremental_limit_is_applied_after_cursor_filter(tmp_path, monkeypatch):
    (tmp_path / "orders.csv").write_text("id,updated_at\n", encoding="utf-8")
    connector = _connector(tmp_path)
    calls = []

    def fake_read(path, nrows=None):
        calls.append(nrows)
        return pd.DataFrame(
            {
                "id": [1, 2, 3],
                "updated_at": ["2026-07-01", "2026-08-01", "2026-08-07"],
            }
        )

    monkeypatch.setattr(connector, "_read_df", fake_read)

    columns, rows = connector.read_table(
        "orders", limit=1, cursor_col="updated_at", since="2026-07-15"
    )

    assert calls == [None]
    assert columns == ["id", "updated_at"]
    assert rows == [(2, "2026-08-01")]


def test_negative_limit_is_rejected(tmp_path):
    (tmp_path / "orders.csv").write_text("id\n1\n", encoding="utf-8")
    connector = _connector(tmp_path)

    with pytest.raises(ValueError, match="不能为负数"):
        connector.read_table("orders", limit=-1)


@pytest.mark.parametrize("cursor_col", [None, "", "   ", 123])
def test_incremental_read_requires_nonempty_cursor_column(tmp_path, cursor_col):
    connector = _connector(tmp_path)

    with pytest.raises(ValueError, match="非空 cursor_col"):
        connector.read_table("orders", cursor_col=cursor_col, since="2026-07-01")


def test_incremental_read_rejects_unknown_cursor_column(tmp_path):
    (tmp_path / "orders.csv").write_text("id,updated_at\n1,2026-08-01\n", encoding="utf-8")
    connector = _connector(tmp_path)

    with pytest.raises(ValueError, match="游标列不存在"):
        connector.read_table("orders", cursor_col="missing", since="2026-07-01")


def test_incremental_read_filters_rows(tmp_path):
    (tmp_path / "orders.csv").write_text(
        "id,updated_at\n1,2026-07-01\n2,2026-08-01\n3,2026-08-07\n",
        encoding="utf-8",
    )
    connector = _connector(tmp_path)

    columns, rows = connector.read_table(
        "orders", cursor_col="updated_at", since="2026-07-15"
    )

    assert columns == ["id", "updated_at"]
    assert rows == [(2, "2026-08-01"), (3, "2026-08-07")]

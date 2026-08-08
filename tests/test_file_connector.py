"""FileConnector 的纯单元测试：目录校验、文件解析、类型归一与增量读取边界。"""

from pathlib import Path

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


def test_negative_limit_is_rejected(tmp_path):
    (tmp_path / "orders.csv").write_text("id\n1\n", encoding="utf-8")
    connector = _connector(tmp_path)

    with pytest.raises(ValueError, match="不能为负数"):
        connector.read_table("orders", limit=-1)


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

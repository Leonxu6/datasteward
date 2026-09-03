from types import SimpleNamespace

import pandas as pd
import pytest

from dm.connect.base import Source
from dm.connect.file import FileConnector, _MAX_COLUMN_NAME


def _connector(tmp_path):
    return FileConnector(Source(name="files", source_type="file", params={"dir": str(tmp_path)}))


def test_normalize_columns_rejects_casefold_collisions():
    df = pd.DataFrame([[1, 2]], columns=["Code", "code"])
    with pytest.raises(ValueError, match="规范化后存在重复"):
        FileConnector._normalize_columns(df)


@pytest.mark.parametrize("column", ["", "   ", "bad\nname", "x" * (_MAX_COLUMN_NAME + 1)])
def test_normalize_columns_rejects_unsafe_names(column):
    df = pd.DataFrame([[1]], columns=[column])
    with pytest.raises(ValueError):
        FileConnector._normalize_columns(df)


def test_column_string_failure_is_redacted():
    class Broken:
        def __str__(self):
            raise RuntimeError("secret-column-token")

    with pytest.raises(ValueError) as exc_info:
        FileConnector._normalize_column_name(Broken())
    assert "secret-column-token" not in str(exc_info.value)
    assert "RuntimeError" in str(exc_info.value)


def test_incremental_compare_error_does_not_echo_since_secret(tmp_path, monkeypatch):
    connector = _connector(tmp_path)
    secret = "sensitive-watermark-value"
    frame = pd.DataFrame({"cursor": [1, 2]})
    monkeypatch.setattr(connector, "_path", lambda name: tmp_path / "data.csv")
    monkeypatch.setattr(connector, "_read_df", lambda *args, **kwargs: frame.copy())
    with pytest.raises(ValueError) as exc_info:
        connector.read_table("data", cursor_col="cursor", since=secret)
    assert secret not in str(exc_info.value)
    assert "since_type=str" in str(exc_info.value)


def test_introspection_redacts_reader_exception_details(tmp_path, monkeypatch):
    connector = _connector(tmp_path)
    path = tmp_path / "orders.csv"
    path.write_text("id\n1\n", encoding="utf-8")
    monkeypatch.setattr(connector, "_read_df", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db-password")))
    with pytest.raises(ValueError) as exc_info:
        connector.introspect()
    assert "db-password" not in str(exc_info.value)
    assert "RuntimeError" in str(exc_info.value)

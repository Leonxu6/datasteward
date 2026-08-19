"""PostgreSQL 连接身份配置的前置校验。"""

import sys

import pytest

from dm.connect.base import Source
from dm.connect.postgres import PostgresConnector


def test_connect_passes_validated_user_and_database_to_driver(monkeypatch):
    captured = {}

    class _FakePsycopg:
        @staticmethod
        def connect(**kwargs):
            captured.update(kwargs)
            return object()

    monkeypatch.setitem(sys.modules, "psycopg", _FakePsycopg)
    connector = PostgresConnector(
        Source(name="pg", source_type="postgres", params={"user": "reader", "db": "warehouse"})
    )
    connector._connect()
    assert captured["user"] == "reader"
    assert captured["dbname"] == "warehouse"


@pytest.mark.parametrize(
    ("field", "value"),
    [("user", None), ("user", ""), ("user", " reader"), ("db", 123), ("db", ""), ("db", "warehouse ")],
)
def test_connect_rejects_invalid_identity_config_before_driver_import(field, value):
    connector = PostgresConnector(Source(name="pg", source_type="postgres", params={field: value}))
    with pytest.raises(ValueError, match=field):
        connector._connect()

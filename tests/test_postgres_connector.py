"""PostgresConnector 的纯单元测试，不需要真实 PostgreSQL。"""

from dm.connect.base import Source
from dm.connect.postgres import PostgresConnector


class _Cursor:
    def __init__(self):
        self.calls = []
        self._responses = iter(
            [
                [("inventory",)],
                [("inventory", "warehouse_id"), ("inventory", "material_id")],
                [
                    ("warehouse_id", "text", "NO"),
                    ("material_id", "text", "NO"),
                    ("qty", "integer", "YES"),
                ],
            ]
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return next(self._responses)


class _Connection:
    def __init__(self):
        self.cursor_obj = _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_obj


def test_introspect_preserves_composite_primary_key_order(monkeypatch):
    connector = PostgresConnector(Source(name="pg", source_type="postgres"))
    fake = _Connection()
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    datasets = connector.introspect(schema="erp")

    assert len(datasets) == 1
    assert datasets[0].primary_key == ["warehouse_id", "material_id"]
    assert [c.is_primary_key for c in datasets[0].columns] == [True, True, False]

    pk_sql, pk_params = fake.cursor_obj.calls[1]
    assert "ORDER BY tc.table_name, kcu.ordinal_position" in pk_sql
    assert pk_params == ("erp",)

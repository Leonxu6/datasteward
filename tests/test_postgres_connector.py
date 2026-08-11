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


def test_introspect_pk_join_matches_full_table_identity(monkeypatch):
    """同 schema 的不同表允许复用约束名时，不能把另一张表的 PK 列串进来。"""
    connector = PostgresConnector(Source(name="pg", source_type="postgres"))
    fake = _Connection()
    monkeypatch.setattr(connector, "_connect", lambda: fake)

    connector.introspect(schema="erp")

    pk_sql, _ = fake.cursor_obj.calls[1]
    normalized = " ".join(pk_sql.split())
    assert "tc.constraint_catalog=kcu.constraint_catalog" in normalized
    assert "tc.constraint_schema=kcu.constraint_schema" in normalized
    assert "tc.constraint_name=kcu.constraint_name" in normalized
    assert "tc.table_catalog=kcu.table_catalog" in normalized
    assert "tc.table_schema=kcu.table_schema" in normalized
    assert "tc.table_name=kcu.table_name" in normalized

import json

from dm.tools import Principal
from dm.tools import data as kernel_data


class _Result:
    def __init__(self, row=(3,), rows=None, description=(("count",),)):
        self.row = row
        self.rows = [] if rows is None else rows
        self.description = description
        self.closed = False

    def fetchone(self):
        return self.row

    def fetchmany(self, size):
        return self.rows[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False


class _Connection:
    def __init__(self, result_factory=None):
        self.results = []
        self.closed = False
        self.result_factory = result_factory or (lambda: _Result())

    def execute(self, sql):
        result = self.result_factory()
        self.results.append(result)
        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False


def test_list_tables_closes_each_cursor_and_connection(monkeypatch):
    connection = _Connection()
    monkeypatch.setattr(kernel_data, "TABLES", [{"name": "material", "cn": "物料", "desc": "demo"}])
    monkeypatch.setattr(kernel_data, "connect_ro", lambda: connection)
    monkeypatch.setattr(kernel_data, "audit_event", lambda *args, **kwargs: None)

    output = json.loads(kernel_data.list_tables(Principal(user="admin", role="管理员")))

    assert output[0]["rows"] == 3
    assert connection.closed is True
    assert connection.results and all(result.closed for result in connection.results)


def test_run_sql_closes_cursor_and_connection_after_fetch(monkeypatch):
    connection = _Connection(
        result_factory=lambda: _Result(rows=[("M001",)], description=(("material_id",),))
    )
    monkeypatch.setattr(kernel_data, "connect_ro", lambda: connection)
    monkeypatch.setattr(kernel_data, "tables_in", lambda sql: ["material"])
    monkeypatch.setattr(kernel_data, "enforce_query", lambda user, sql, tables: {
        "allow": True,
        "mask_columns": [],
        "hit_markings": [],
    })
    monkeypatch.setattr(kernel_data, "apply_row_policies", lambda user, sql, tables: sql)
    monkeypatch.setattr(kernel_data, "apply_mask", lambda columns, rows, masks: (rows, []))
    monkeypatch.setattr(kernel_data, "audit_event", lambda *args, **kwargs: None)

    output = json.loads(kernel_data.run_sql(Principal(user="admin", role="管理员"), "SELECT material_id FROM material"))

    assert output["rows"] == [{"material_id": "M001"}]
    assert connection.closed is True
    assert connection.results and all(result.closed for result in connection.results)

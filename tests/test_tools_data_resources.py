import json

from dm.tools import Principal
from dm.tools import data as kernel_data


class _Result:
    description = (("count",),)

    def __init__(self, row=(3,)):
        self.row = row
        self.closed = False

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True
        return False


class _Connection:
    def __init__(self):
        self.results = []
        self.closed = False

    def execute(self, sql):
        result = _Result()
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

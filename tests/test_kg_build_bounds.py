from contextlib import nullcontext

import pytest

from dm.kg import build


class Result:
    def __init__(self, columns, rows):
        self.description = [(column,) for column in columns]
        self.rows = list(rows)
        self.fetch_sizes = []
        self.closed = False

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        batch, self.rows = self.rows[:size], self.rows[size:]
        return batch

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class Warehouse:
    def __init__(self, tables):
        self.tables = tables
        self.results = []
        self.closed = False

    def execute(self, sql):
        name = sql.split("`")[1]
        columns, rows = self.tables[name]
        result = Result(columns, rows)
        self.results.append(result)
        return result

    def close(self):
        self.closed = True


class Session:
    def __init__(self):
        self.calls = []

    def run(self, query, **kwargs):
        self.calls.append((query, kwargs))


class Driver:
    def __init__(self):
        self.value = Session()
        self.closed = False

    def session(self):
        return nullcontext(self.value)

    def close(self):
        self.closed = True


def test_skeleton_streams_nodes_and_edges_in_bounded_batches(monkeypatch):
    parent_rows = [("P1",), ("P2",)]
    child_rows = [(f"C{index}", "P1") for index in range(501)]
    warehouse = Warehouse({
        "parent": (["id"], parent_rows),
        "child": (["id", "parent_id"], child_rows),
    })
    driver = Driver()
    schemas = {
        "parent": {"pk": "id", "cn": "父", "fks": []},
        "child": {"pk": "id", "cn": "子", "fks": [("parent_id", "parent")]},
    }
    monkeypatch.setattr(build, "KG_TABLES", ["parent", "child"])
    monkeypatch.setattr(build, "_KGSET", {"parent", "child"})
    monkeypatch.setattr(build, "table_by_name", schemas.__getitem__)
    monkeypatch.setattr(build, "connect_ro", lambda: warehouse)
    monkeypatch.setattr("dm.kg.store.driver", lambda: driver)

    assert build.skeleton(verbose=False) == (503, 501)

    payloads = [
        values[key]
        for _, values in driver.value.calls
        for key in ("recs", "edges")
        if key in values
    ]
    assert payloads
    assert max(map(len, payloads)) <= build._KG_BATCH_SIZE
    assert all(size == build._KG_BATCH_SIZE for result in warehouse.results for size in result.fetch_sizes)
    assert all(result.closed for result in warehouse.results)
    assert warehouse.closed
    assert driver.closed


class PgCursor:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.fetch_sizes = []
        self.closed = False

    def execute(self, _sql):
        return None

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        batch, self.rows = self.rows[:size], self.rows[size:]
        return batch

    def close(self):
        self.closed = True


class PgConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


def test_extract_streams_registry_and_closes_every_resource(monkeypatch):
    rows = [(f"DOC-{index}", f"title {index}", None, "") for index in range(501)]
    cursor = PgCursor(rows)
    connection = PgConnection(cursor)
    driver = Driver()
    monkeypatch.setattr("psycopg2.connect", lambda **_kwargs: connection)
    monkeypatch.setattr("dm.kg.store.driver", lambda: driver)
    monkeypatch.setattr(build, "_document_body", lambda _path, title: title)
    monkeypatch.setattr(build, "_llm_extract", lambda *_args: [])

    assert build.extract(verbose=False) == (501, 0)
    assert cursor.fetch_sizes == [build._KG_BATCH_SIZE, build._KG_BATCH_SIZE]
    assert cursor.closed
    assert connection.closed
    assert driver.closed


def test_skeleton_closes_driver_when_warehouse_connection_fails(monkeypatch):
    driver = Driver()
    monkeypatch.setattr("dm.kg.store.driver", lambda: driver)
    monkeypatch.setattr(build, "connect_ro", lambda: (_ for _ in ()).throw(RuntimeError("offline")))

    with pytest.raises(RuntimeError, match="offline"):
        build.skeleton(verbose=False)

    assert driver.closed


def test_extract_closes_database_when_graph_driver_fails(monkeypatch):
    cursor = PgCursor()
    connection = PgConnection(cursor)
    monkeypatch.setattr("psycopg2.connect", lambda **_kwargs: connection)
    monkeypatch.setattr("dm.kg.store.driver", lambda: (_ for _ in ()).throw(RuntimeError("offline")))

    with pytest.raises(RuntimeError, match="offline"):
        build.extract(verbose=False)

    assert cursor.closed
    assert connection.closed


@pytest.mark.parametrize("size", [True, 0, -1, 1.5, "500"])
def test_fetch_batches_rejects_invalid_sizes(size):
    with pytest.raises(ValueError, match="positive integer"):
        list(build._fetch_batches(PgCursor(), size=size))


def test_fetch_batches_rejects_malformed_driver_results():
    class BadCursor:
        def fetchmany(self, _size):
            return object()

    with pytest.raises(RuntimeError, match="malformed batch"):
        list(build._fetch_batches(BadCursor()))

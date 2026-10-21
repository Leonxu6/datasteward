from dm.app import data


def _call(fn):
    return getattr(fn, "__wrapped__", fn)()


def test_flink_probe_redacts_backend_exception(monkeypatch):
    import requests

    def boom(*args, **kwargs):
        raise RuntimeError("token=super-secret")

    monkeypatch.setattr(requests, "get", boom)
    result = _call(data.flink_status)
    assert result["ok"] is False
    assert "super-secret" not in result["error"]
    assert "RuntimeError" in result["error"]


class _Response:
    def __init__(self, payload, *, status_error=None):
        self.payload = payload
        self.status_error = status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


def test_flink_probe_checks_http_status_before_using_payload(monkeypatch):
    import requests

    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: _Response({}, status_error=RuntimeError("token=secret")),
    )

    result = _call(data.flink_status)

    assert result["ok"] is False
    assert result["jobs"] == []
    assert "secret" not in result["error"]


def test_flink_probe_rejects_oversized_job_catalog(monkeypatch):
    import requests

    responses = iter(
        [
            _Response({"flink-version": "1.18"}),
            _Response({"jobs": [{}] * (data._MAX_FLINK_JOBS + 1)}),
        ]
    )
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: next(responses))

    result = _call(data.flink_status)

    assert result["ok"] is False
    assert result["jobs"] == []


def test_flink_probe_rejects_malformed_job_tasks(monkeypatch):
    import requests

    responses = iter(
        [
            _Response({}),
            _Response({"jobs": [{"jid": "job-1", "tasks": []}]}),
        ]
    )
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: next(responses))

    result = _call(data.flink_status)

    assert result["ok"] is False
    assert result["jobs"] == []


def test_pg_slot_probe_reads_one_bounded_page(monkeypatch):
    import psycopg

    class Cursor:
        def __init__(self):
            self.requested = None

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _query):
            return None

        def fetchmany(self, size):
            self.requested = size
            return [("slot_a", True, 7)]

    class Connection:
        def __init__(self, cursor):
            self._cursor = cursor

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return self._cursor

    cursor = Cursor()
    monkeypatch.setattr(psycopg, "connect", lambda **kwargs: Connection(cursor))

    result = _call(data.pg_slots)

    assert result["ok"] is True
    assert result["slots"] == [{"name": "slot_a", "active": True, "lag": 7}]
    assert cursor.requested == data._MAX_PG_SLOTS + 1


def test_pg_slot_probe_rejects_oversized_catalog(monkeypatch):
    import psycopg

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _query):
            return None

        def fetchmany(self, size):
            return [(f"slot_{index}", False, None) for index in range(size)]

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def cursor(self):
            return Cursor()

    monkeypatch.setattr(psycopg, "connect", lambda **kwargs: Connection())

    result = _call(data.pg_slots)

    assert result["ok"] is False
    assert result["slots"] == []
    assert "ValueError" in result["error"]


def test_warehouse_probe_redacts_backend_exception(monkeypatch):
    from dm.warehouse import store

    def boom():
        raise RuntimeError("password=warehouse-secret")

    monkeypatch.setattr(store, "connect_ro", boom)
    result = _call(data.wh_health)
    assert result["ok"] is False
    assert "warehouse-secret" not in result["error"]
    assert "RuntimeError" in result["error"]


def test_warehouse_probe_closes_connection_when_query_fails(monkeypatch):
    from dm.warehouse import store

    class BrokenConnection:
        def __init__(self):
            self.closed = False

        def execute(self, query):
            raise RuntimeError("password=query-secret")

        def close(self):
            self.closed = True

    connection = BrokenConnection()
    monkeypatch.setattr(store, "connect_ro", lambda: connection)

    result = _call(data.wh_health)

    assert result["ok"] is False
    assert connection.closed is True
    assert "query-secret" not in result["error"]

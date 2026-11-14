import json
from decimal import Decimal

import pytest

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
    def __init__(self, payload=None, *, raw=None, status_error=None):
        self.raw = raw if raw is not None else json.dumps(payload).encode("utf-8")
        self.status_error = status_error
        self.closed = False

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.raw), chunk_size):
            yield self.raw[offset:offset + chunk_size]

    def close(self):
        self.closed = True


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


def test_flink_probe_streams_bounded_responses_and_closes_them(monkeypatch):
    import requests

    overview = _Response({"flink-version": "1.18"})
    jobs = _Response({"jobs": []})
    responses = iter([overview, jobs])
    calls = []

    def fake_get(*args, **kwargs):
        calls.append((args, kwargs))
        return next(responses)

    monkeypatch.setattr(requests, "get", fake_get)

    result = _call(data.flink_status)

    assert result["ok"] is True
    assert overview.closed is True
    assert jobs.closed is True
    assert [kwargs for _args, kwargs in calls] == [
        {"stream": True, "timeout": 5},
        {"stream": True, "timeout": 5},
    ]


def test_flink_probe_rejects_oversized_response_body(monkeypatch):
    import requests

    response = _Response(raw=b"{" + b" " * data._MAX_FLINK_RESPONSE_BYTES + b"}")
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)

    result = _call(data.flink_status)

    assert result["ok"] is False
    assert result["jobs"] == []
    assert response.closed is True


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


def test_flink_probe_does_not_publish_partially_valid_jobs(monkeypatch):
    import requests

    responses = iter(
        [
            _Response({}),
            _Response({"jobs": [{"jid": "valid", "tasks": {}}, {"jid": "bad", "tasks": []}]}),
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


def test_pg_slot_probe_preserves_decimal_integer_lag():
    assert data._pg_slot_row(("slot_a", False, Decimal("42"))) == {
        "name": "slot_a",
        "active": False,
        "lag": 42,
    }


def test_pg_slot_probe_rejects_coercible_or_invalid_row_values():
    invalid_rows = (
        ("slot_a", "false", 0),
        ("slot_a", True, -1),
        ("slot_a", True, Decimal("1.5")),
        (" slot_a", True, 0),
    )
    for row in invalid_rows:
        with pytest.raises(ValueError):
            data._pg_slot_row(row)


def test_pg_slot_probe_does_not_publish_partial_rows(monkeypatch):
    import psycopg

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _query):
            return None

        def fetchmany(self, _size):
            return [("slot_a", True, 0), ("slot_b", "false", 1)]

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

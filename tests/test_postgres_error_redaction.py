from dm.connect.base import Source
from dm.connect.postgres import PostgresConnector


def test_connection_failure_redacts_driver_details(monkeypatch):
    connector = PostgresConnector(Source(name="pg", source_type="postgres"))
    monkeypatch.setattr(
        connector,
        "_connect",
        lambda: (_ for _ in ()).throw(RuntimeError("postgres://user:secret@host/db")),
    )

    ok, message = connector.test_connection()

    assert ok is False
    assert message == "PostgreSQL connection failed (RuntimeError)"
    assert "secret" not in message
    assert "host" not in message

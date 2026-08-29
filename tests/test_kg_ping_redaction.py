from dm.kg import store


def test_ping_redacts_backend_exception_details(monkeypatch):
    def fail(_query):
        raise RuntimeError("bolt://user:secret@example.invalid leaked")

    monkeypatch.setattr(store, "run_read", fail)

    ok, detail = store.ping()

    assert ok is False
    assert detail == "Neo4j health check failed (RuntimeError)"
    assert "secret" not in detail

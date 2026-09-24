from dm.kg import store


def test_ping_accepts_exact_health_probe(monkeypatch):
    monkeypatch.setattr(store, "run_read", lambda cypher: [{"ok": 1}])
    assert store.ping() == (True, "")


def test_ping_rejects_malformed_health_probe(monkeypatch):
    for rows in ([], [{"ok": True}], [{"ok": 0}], [{"other": 1}], [{"ok": 1}, {"ok": 1}], ["ok"]):
        monkeypatch.setattr(store, "run_read", lambda cypher, rows=rows: rows)
        ok, detail = store.ping()
        assert ok is False
        assert detail == "Neo4j health check returned an unexpected response"


def test_ping_reports_probe_exception_without_backend_detail(monkeypatch):
    def fail(_cypher):
        raise RuntimeError("neo4j://secret.internal")

    monkeypatch.setattr(store, "run_read", fail)
    ok, detail = store.ping()
    assert ok is False
    assert detail == "Neo4j health check failed (RuntimeError)"
    assert "secret.internal" not in detail

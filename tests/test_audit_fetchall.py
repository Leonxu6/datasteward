from scripts.audit_fetchall import audit_source


def test_fetchall_audit_allows_batched_fetches():
    assert audit_source("cursor.fetchmany(500)\n") == []


def test_fetchall_audit_reports_full_materialization():
    assert audit_source("cursor.fetchall()\n") == ["fetchall() can materialize an unbounded result on line 1"]

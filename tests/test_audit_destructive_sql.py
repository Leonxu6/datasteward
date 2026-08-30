from scripts.audit_destructive_sql import audit_source


def test_destructive_sql_audit_allows_scoped_delete():
    assert audit_source("cursor.execute('DELETE FROM jobs WHERE id = %s', (job_id,))\n") == []


def test_destructive_sql_audit_reports_unscoped_delete():
    assert audit_source("cursor.execute('DELETE FROM jobs')\n") == ["destructive literal SQL on line 1"]

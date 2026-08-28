from scripts.audit_sql_interpolation import audit_source


def test_sql_interpolation_audit_allows_parameterized_query():
    assert audit_source("cursor.execute('select * from t where id=%s', (item_id,))\n") == []


def test_sql_interpolation_audit_reports_fstring_query():
    assert audit_source("cursor.execute(f'select * from {table}')\n") == [
        "interpolated SQL passed to execute() on line 1; use driver parameters or validated identifiers"
    ]

from scripts.audit_pandas_read_sql import audit_source


def test_pandas_sql_audit_allows_chunksize():
    assert audit_source("pd.read_sql_query(sql, conn, chunksize=1000)\n") == []


def test_pandas_sql_audit_reports_full_materialization():
    assert audit_source("pd.read_sql_query(sql, conn)\n") == ["pandas.read_sql_query() without chunksize on line 1"]

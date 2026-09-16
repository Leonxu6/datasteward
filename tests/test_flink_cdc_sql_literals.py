from dm.pipeline import gen_flink_cdc_sql as gen
from dm.schema import TABLES


def test_sql_string_doubles_single_quotes():
    assert gen._sql_string("plain") == "'plain'"
    assert gen._sql_string("o'reilly") == "'o''reilly'"


def test_source_ddl_escapes_dynamic_connection_options(monkeypatch):
    monkeypatch.setitem(gen.PG, "host", "pg'edge")
    monkeypatch.setitem(gen.PG, "user", "reader'ops")
    monkeypatch.setitem(gen.PG, "pw", "pa'ss")
    ddl = gen.src_ddl(TABLES[0])
    assert "'hostname' = 'pg''edge'" in ddl
    assert "'username' = 'reader''ops'" in ddl
    assert "'password' = 'pa''ss'" in ddl


def test_sink_ddl_escapes_dynamic_connection_options(monkeypatch):
    monkeypatch.setitem(gen.SR, "jdbc", "jdbc:mysql://sr'edge:9030")
    monkeypatch.setitem(gen.SR, "db", "warehouse'prod")
    ddl = gen.sink_ddl(TABLES[0])
    assert "'jdbc-url' = 'jdbc:mysql://sr''edge:9030'" in ddl
    assert "'database-name' = 'warehouse''prod'" in ddl

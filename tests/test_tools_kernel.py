"""治理内核（dm/tools）确定性单测：SQL 守卫、Principal 映射、PBAC 拒答路径（不触 DB）。"""
import json

import pytest

from dm.tools import Principal
from dm.tools.sql_guard import MAX_SQL_CHARS, tables_in, validate_readonly


def test_validate_readonly_rejects_writes():
    _, err = validate_readonly("DELETE FROM material")
    assert err and "SELECT" in err
    _, err = validate_readonly("SELECT 1; SELECT 2")
    assert err and "单条" in err
    _, err = validate_readonly("SELECT * FROM material WHERE 1=1 UNION SELECT 1 FROM mysql.user; DROP TABLE x")
    assert err
    clean, err = validate_readonly("  SELECT material_id FROM material ; ")
    assert err is None and clean.startswith("SELECT")


def test_validate_readonly_blocks_forbidden_keywords():
    _, err = validate_readonly("SELECT 1 FROM t WHERE x IN (SELECT y FROM z) UNION ALL SELECT truncate_me FROM w")
    # truncate 作为独立词才拦；这里 truncate_me 不是独立词，不应误拦
    assert err is None
    _, err = validate_readonly("WITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a")
    assert err


def test_sql_guard_normalizes_non_string_inputs():
    clean, err = validate_readonly(None)
    assert clean == ""
    assert err == "ERROR: SQL 必须是字符串。"
    with pytest.raises(TypeError, match="sql must be a string"):
        tables_in(123)


def test_validate_readonly_rejects_oversized_queries_before_regex_work():
    clean, err = validate_readonly("SELECT '" + ("x" * MAX_SQL_CHARS) + "'")
    assert clean == ""
    assert err and "SQL 过长" in err
    assert str(MAX_SQL_CHARS) in err


def test_validate_readonly_rejects_unsafe_control_characters():
    for sql in ("SELECT\x00 1", "SELECT\x1f 1", "SELECT\x7f 1"):
        clean, err = validate_readonly(sql)
        assert clean == ""
        assert err and "控制字符" in err
    clean, err = validate_readonly("SELECT\n1\tFROM material")
    assert err is None
    assert "material" in tables_in(clean)


def test_tables_in_matches_word_boundary():
    ts = tables_in("SELECT * FROM material JOIN inventory ON 1=1")
    assert "material" in ts and "inventory" in ts
    # material_category 不应因包含 material 而把 material 也算进去——按词边界应各自独立识别
    ts2 = tables_in("SELECT * FROM material_category")
    assert "material_category" in ts2


def test_describe_table_rejects_malformed_names_before_schema_lookup(monkeypatch):
    from dm.tools import data as kernel_data

    def _boom(name):
        raise AssertionError("invalid names must not reach table_by_name")

    monkeypatch.setattr(kernel_data, "table_by_name", _boom)
    monkeypatch.setattr(kernel_data, "audit_event", lambda *args, **kwargs: None)
    principal = Principal(user="admin", role="管理员")
    for name in (None, "", " material", "material ", "material;drop", "bad\x00name"):
        out = kernel_data.describe_table(principal, name)
        assert out.startswith("ERROR")
        assert "table name" in out


def test_principal_to_user_maps_attrs():
    p = Principal(user="w1", role="仓管", purpose="盘点", session_id="S1", channel="test", warehouse_id="W02")
    u = p.to_user()
    assert u.name == "w1" and u.role == "仓管" and u.purpose == "盘点"
    assert u.attrs.get("warehouse_id") == "W02"
    p2 = Principal(user="a", role="管理员")
    assert p2.to_user().attrs == {}


def test_run_sql_pbac_deny_before_db(tmp_path, monkeypatch):
    """仓管显式查 credit_limit（FIN 列）→ 在连 DB 之前就被 enforce_query 拒绝并留审计。"""
    from dm.tools import data as kernel_data

    def _boom():
        raise AssertionError("被拒查询不应触达数据库连接")

    monkeypatch.setattr(kernel_data, "connect_ro", _boom)
    p = Principal(user="w1", role="仓管", purpose="", session_id="S-test-deny", channel="test")
    out = kernel_data.run_sql(p, "SELECT credit_limit FROM customer")
    assert "权限不足" in out and "credit_limit" in out

    from dm.warehouse.store import read_log
    recs = [r for r in read_log("audit_log") if r["session_id"] == "S-test-deny"]
    assert recs, "拒绝也必须留审计"
    rec = recs[-1]
    assert rec["decision"] == "deny" and rec["category"] == "authorizationCheck"
    assert rec["role"] == "仓管" and rec["tool_name"] == "run_sql"
    assert "FIN" in rec["markings"]
    assert json.loads(rec["tool_args"])["sql"].startswith("SELECT")


def test_run_sql_guard_deny_audited():
    p = Principal(user="x", role="管理员", purpose="财务对账", session_id="S-test-guard", channel="test")
    from dm.tools import data as kernel_data
    out = kernel_data.run_sql(p, "DROP TABLE material")
    assert out.startswith("ERROR")
    from dm.warehouse.store import read_log
    recs = [r for r in read_log("audit_log") if r["session_id"] == "S-test-guard"]
    assert recs and recs[-1]["ok"] is False

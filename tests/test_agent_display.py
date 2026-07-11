"""钉钉推送文案单测：工具调用意图行（_fmt_tool）与执行回执（_fmt_receipt）。

约束（决议见 PR）：推送层绝不出现裸 SQL/JSON 原文；错误与权限拦截必须如实可见；
describe/list 类成功静默防刷屏。审计日志留痕（原始参数全文）不经这两个函数、不受影响。
"""
import json

from dm.agent.core import _fmt_receipt, _fmt_tool


# ---------------- 意图行 _fmt_tool ----------------

def test_run_sql_shows_cn_table_names_not_sql():
    sql = ("SELECT m.material_id, i.qty FROM inventory i "
           "JOIN material m ON i.material_id = m.material_id "
           "JOIN warehouse w ON i.warehouse_id = w.warehouse_id "
           "LEFT JOIN storage_location sl ON i.location_id = sl.location_id LIMIT 200")
    line = _fmt_tool("run_sql", {"sql": sql})
    assert "SELECT" not in line and "JOIN" not in line and "\n" not in line
    for cn in ("即时库存信息", "物料信息", "仓库", "库位"):
        assert cn in line


def test_run_sql_dedupes_and_keeps_unknown_table_raw():
    sql = "SELECT * FROM dm_dw.ads_shortage_analysis a JOIN dm_dw.ads_shortage_analysis b ON 1=1"
    line = _fmt_tool("run_sql", {"sql": sql})
    assert line.count("dm_dw.ads_shortage_analysis") == 1


def test_run_sql_backtick_and_case_insensitive():
    line = _fmt_tool("run_sql", {"sql": "select qty from `inventory` where 1=1"})
    assert "即时库存信息" in line


def test_run_sql_no_table_fallback():
    assert _fmt_tool("run_sql", {"sql": "SELECT 1"}) == "🔍 正在执行数据查询…"


def test_mcp_prefixed_name_compatible():
    # claude 旧路径工具名带 mcp__dm__ 前缀，须同样人话化
    assert _fmt_tool("mcp__dm__list_tables", {}) == "🔍 我先看看数据仓库里有哪些表"


def test_describe_table_cn():
    line = _fmt_tool("describe_table", {"name": "inventory"})
    assert "即时库存信息" in line and "inventory" in line


def test_graph_query_mode_cn():
    line = _fmt_tool("graph_query", {"mode": "impact_path", "entity_id": "S001"})
    assert "影响链路" in line and "S001" in line


def test_execute_action_mentions_approval():
    line = _fmt_tool("execute_action", {"action": "adjust_safety_stock"})
    assert "adjust_safety_stock" in line and "审批" in line


def test_unknown_tool_no_json_dump():
    line = _fmt_tool("brand_new_tool", {"secret": "x" * 500})
    assert line == "🔧 brand_new_tool"


# ---------------- 回执 _fmt_receipt ----------------

def test_receipt_run_sql_row_count():
    res = json.dumps({"columns": ["a"], "row_count": 42, "rows": []})
    assert "42 行" in _fmt_receipt("run_sql", res)


def test_receipt_run_sql_unparsable_still_ok():
    r = _fmt_receipt("run_sql", "not-json")
    assert r.startswith("✅")


def test_receipt_error_visible():
    r = _fmt_receipt("run_sql", "ERROR: 查询失败: (1064, \"Column cannot be resolved\")")
    assert r.startswith("⚠️")


def test_receipt_permission_denied_relays_kernel_reason():
    r = _fmt_receipt("run_sql", "⛔ 权限不足：角色『访客』无权查询 inventory\n详情……")
    assert r.startswith("⛔") and "权限不足" in r and "\n" not in r


def test_receipt_search_documents_count():
    res = json.dumps([{"doc_id": "D1"}, {"doc_id": "D2"}, {"doc_id": "D3"}])
    assert "3 篇" in _fmt_receipt("mcp__dm__search_documents", res)


def test_receipt_action_pending_approval():
    res = json.dumps({"ok": False, "status": "pending_approval", "preview": {}})
    assert "待审批" in _fmt_receipt("execute_action", res)


def test_receipt_action_ok():
    assert _fmt_receipt("execute_action", json.dumps({"ok": True})) == "✅ 治理动作已执行"


def test_receipt_action_json_error_field():
    res = json.dumps({"ok": False, "error": "提交条件不满足：现有库存 < 发货量"})
    assert _fmt_receipt("execute_action", res).startswith("⚠️")


def test_receipt_action_permission_denied_pretty_json():
    # 复刻生产真实形态：内核返回 indent=2 的美化 JSON（首行只有 "{"），
    # 权限拒绝的回执必须转述 error 文案，绝不能推出 "{" 之类的残片
    res = json.dumps({"ok": False, "action_id": "ACT1",
                      "error": "权限不足：角色『仓管』无权执行『adjust_safety_stock』（需 ['管理员'] 之一）"},
                     ensure_ascii=False, indent=2)
    r = _fmt_receipt("execute_action", res)
    assert r.startswith("⛔") and "仓管" in r and "{" not in r


def test_receipt_describe_and_list_silent_on_success():
    assert _fmt_receipt("describe_table", json.dumps({"table": "material"})) == ""
    assert _fmt_receipt("list_tables", "[]") == ""
    assert _fmt_receipt("list_metrics", "[]") == ""


def test_receipt_describe_error_still_visible():
    # 静默只对成功生效：describe/list 失败必须可见
    assert _fmt_receipt("describe_table", "ERROR: 表不存在").startswith("⚠️")

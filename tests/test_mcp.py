"""MCP 连接器集成测试：拉起 stdio 子进程(python -m dm.connector.mcp_server)，
列/调工具、验证审计留痕、且写/DDL 被拒。无需 claude，确定性。"""

import pytest

pytestmark = pytest.mark.stack  # 需要可达的 StarRocks/Postgres 栈；不可达自动跳过
import asyncio
import os
import sys
from pathlib import Path

import dm
from dm.warehouse.store import read_log
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SRC = str(Path(dm.__file__).resolve().parent.parent)


async def _run():
    env = {**os.environ, "DM_SESSION_ID": "test-001", "DM_CHANNEL": "test",
           "PYTHONPATH": SRC, "PYTHONUTF8": "1"}
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "dm.connector.mcp_server"], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            assert {"list_tables", "describe_table", "run_sql"} <= tools

            await session.call_tool("list_tables", {})
            await session.call_tool("describe_table", {"name": "inventory"})

            r = await session.call_tool("run_sql", {
                "sql": "SELECT SUM(qty) AS total FROM inventory WHERE material_id='M0001'"})
            assert "12" in r.content[0].text

            r = await session.call_tool("run_sql", {"sql": "DELETE FROM inventory"})
            assert r.content[0].text.startswith("ERROR")

            r = await session.call_tool("run_sql", {"sql": "ATTACH 'evil.db'"})
            assert r.content[0].text.startswith("ERROR")


def test_mcp_connector_and_audit():
    asyncio.run(_run())
    audit = [e for e in read_log("audit_log") if e.get("session_id") == "test-001"]
    # list_tables + describe_table + run_sql×3 = 5 条审计
    assert len(audit) >= 5
    assert any(not e["ok"] for e in audit)  # 写/DDL 被拒并留痕

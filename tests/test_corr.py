"""审计↔任务链按 session 关联，并验证 MCP 子进程(-m dm.connector.mcp_server)
被真实拉起（audit 出现新行）。需要 claude，标 integration。"""

import pytest

from dm.agent import run_agent
from dm.warehouse.store import read_log

pytestmark = pytest.mark.stack  # 需要可达的 StarRocks/Postgres 栈；不可达自动跳过


@pytest.mark.integration
def test_audit_and_session_correlate():
    r = run_agent("物料 M0001 现在总库存多少？", channel="test")
    sid = r["session_id"]
    sess = [s for s in read_log("agent_session") if s.get("session_id") == sid]
    audit = [a for a in read_log("audit_log") if a.get("session_id") == sid]
    assert any(s.get("step_type") == "question" for s in sess)
    assert any(s.get("step_type") == "answer" for s in sess)
    assert len(audit) >= 1  # 智能体至少经 MCP 连接器查过一次仓库

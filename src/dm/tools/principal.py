"""访问主体 Principal：治理内核的显式身份载体。

原 MCP 服务器靠环境变量（DM_USER/DM_ROLE/DM_PURPOSE/DM_SESSION_ID/DM_CHANNEL）传身份，
只适用于"每会话一个子进程"的形态。治理内核改为**显式传参**：谁调用、什么角色、什么目的、
哪个会话，一律随调用传入——同一份 PBAC/审计代码既服务进程内的 LangGraph 智能体，
也服务对外的 stdio MCP 壳（后者用 principal_from_env() 兼容旧注入路径）。
"""
import os
from dataclasses import dataclass
from datetime import datetime

from dm.security import User


@dataclass(frozen=True)
class Principal:
    """一次访问的完整主体：用户 + 角色 + 目的（PBAC）+ 会话关联 + 行级属性。"""
    user: str = "agent"
    role: str = "仓管"
    purpose: str = ""
    session_id: str = ""
    channel: str = "cli"
    warehouse_id: str = ""     # 行级策略属性（仓管的管辖仓库）

    def to_user(self) -> User:
        """转成权限引擎的 User（dm.security.model.User）。"""
        attrs = {"warehouse_id": self.warehouse_id} if self.warehouse_id else {}
        return User(name=self.user, role=self.role, purpose=self.purpose, attrs=attrs)


def principal_from_env() -> Principal:
    """从环境变量构建 Principal（stdio MCP 壳用；与旧 mcp_server 的 env 注入契约一致）。"""
    return Principal(
        user=os.environ.get("DM_USER", "anonymous"),
        role=os.environ.get("DM_ROLE", "仓管"),
        purpose=os.environ.get("DM_PURPOSE", ""),
        session_id=os.environ.get("DM_SESSION_ID") or ("mcp-" + datetime.now().strftime("%Y%m%d%H%M%S")),
        channel=os.environ.get("DM_CHANNEL", "mcp"),
        warehouse_id=os.environ.get("DM_WAREHOUSE", ""),
    )

"""访问主体 Principal：治理内核的显式身份载体。

身份、角色、目的、会话和通道都会进入 PBAC 与审计，因此在 Principal 构造时做稳定的
长度/控制字符/通道格式校验，避免脏环境变量或外部通道字段污染授权与日志。
"""
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from dm.security import User
from dm.tools.identity import normalize_channel, normalize_identity_text


@dataclass(frozen=True)
class Principal:
    """一次访问的完整主体：用户 + 角色 + 目的 + 会话关联 + 行级属性。"""

    user: str = "agent"
    role: str = "仓管"
    purpose: str = ""
    session_id: str = ""
    channel: str = "cli"
    warehouse_id: str = ""

    def __post_init__(self):
        normalize_identity_text(self.user, field_name="user", max_length=200, allow_empty=False)
        normalize_identity_text(self.role, field_name="role", max_length=100, allow_empty=False)
        normalize_identity_text(self.purpose, field_name="purpose", max_length=500, allow_empty=True)
        normalize_identity_text(self.session_id, field_name="session_id", max_length=200, allow_empty=True)
        normalize_channel(self.channel, default="cli")
        normalize_identity_text(self.warehouse_id, field_name="warehouse_id", max_length=100, allow_empty=True)

    def to_user(self) -> User:
        """转成权限引擎的 User。"""
        attrs = {"warehouse_id": self.warehouse_id} if self.warehouse_id else {}
        return User(name=self.user, role=self.role, purpose=self.purpose, attrs=attrs)


def _generated_session_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"mcp-{timestamp}-{secrets.token_hex(6)}"


def principal_from_env() -> Principal:
    """从环境变量构建 Principal（stdio MCP 壳兼容路径）。"""
    session_id = os.environ.get("DM_SESSION_ID")
    if session_id is None or session_id == "":
        session_id = _generated_session_id()
    return Principal(
        user=os.environ.get("DM_USER", "anonymous"),
        role=os.environ.get("DM_ROLE", "仓管"),
        purpose=os.environ.get("DM_PURPOSE", ""),
        session_id=session_id,
        channel=os.environ.get("DM_CHANNEL", "mcp"),
        warehouse_id=os.environ.get("DM_WAREHOUSE", ""),
    )

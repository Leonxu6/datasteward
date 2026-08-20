"""连接器框架（对标 Palantir Data Connection）。

Palantir 四对象模型 → 我们的落地：
- **Source**  连接实例 = 连接参数 + **凭据引用（不内联）** + **源打标 Markings** + 描述。
              凭据只存"环境变量名"，值从 env 取，绝不写进代码/配置（对标 Palantir 凭据保管）。
- **Connector** 某类源系统的集成器（子类）：`introspect()` 自省 schema、`read_table()` 抽数。
- **Sync**    一次搬数动作：snapshot（全量替换）/ incremental（游标 APPEND）/ cdc（Flink 流）。
- **源打标传播**：Source 的 markings 会随抽数落到 raw 数据集，并沿血缘继续向下游传播（见 security/ 与 pipeline/lineage）。

见 docs/palantir/01-数据连接层-Data-Connection.md。真实客户源为用友 U8/SQL Server，
先用现有 PostgreSQL 影子源当"模拟客户库"跑通，U8 连接器接口预留、待真库。
"""
import operator
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from dm.connect.validation import normalize_env_name


class SyncMode(str, Enum):
    SNAPSHOT = "snapshot"        # 全量替换（源不支持增量时）
    INCREMENTAL = "incremental"  # 单调游标增量（APPEND 风格）
    CDC = "cdc"                  # 流式变更捕获（我们由 Flink CDC 承担）


def normalize_read_limit(limit: Optional[int]) -> Optional[int]:
    """规范化 read_table 的行数上限；0 合法，负数、布尔值和非整数立即拒绝。"""
    if limit is None:
        return None
    if isinstance(limit, bool):
        raise ValueError(f"limit 必须是整数，不能是布尔值: {limit!r}")
    try:
        value = operator.index(limit)
    except TypeError as exc:
        raise ValueError(f"limit 必须是整数: {limit!r}") from exc
    if value < 0:
        raise ValueError(f"limit 不能为负数: {value}")
    return value


def _normalize_positive_int(value, *, default=None, field_name: str) -> int:
    """解析配置中的正整数，接受 int / ASCII 数字字符串，拒绝布尔值、截断和首尾空白。"""
    value = default if value is None else value
    if isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是正整数，不能是布尔值: {value!r}")
    if isinstance(value, str):
        if not value or value != value.strip() or not value.isascii() or not value.isdecimal():
            raise ValueError(f"{field_name} 必须是正整数: {value!r}")
        parsed = int(value)
    else:
        try:
            parsed = operator.index(value)
        except TypeError as exc:
            raise ValueError(f"{field_name} 必须是正整数: {value!r}") from exc
    if parsed <= 0:
        raise ValueError(f"{field_name} 必须大于 0: {parsed}")
    return parsed


def normalize_port(port, *, default=None) -> int:
    """规范化 TCP 端口，允许整数或 ASCII 数字字符串，并拒绝隐式截断与越界值。"""
    parsed = _normalize_positive_int(port, default=default, field_name="port")
    if parsed > 65535:
        raise ValueError(f"port 超出范围 1-65535: {parsed}")
    return parsed


def normalize_timeout(timeout, *, default=15) -> int:
    """规范化连接超时秒数，要求正整数，避免 bool/float 被驱动静默解释。"""
    return _normalize_positive_int(timeout, default=default, field_name="connect_timeout")


@dataclass
class ColumnDef:
    """自省得到的一列。"""
    name: str
    data_type: str
    nullable: bool = True
    is_primary_key: bool = False


@dataclass
class DatasetDef:
    """自省得到的一张源表定义 —— 将落为一个 **raw 数据集**。"""
    name: str
    columns: list = field(default_factory=list)
    primary_key: list = field(default_factory=list)
    row_estimate: Optional[int] = None

    def col_names(self):
        return [c.name for c in self.columns]


@dataclass
class Source:
    """治理化的连接源。凭据不内联——`credential_env` 只存环境变量名。"""
    name: str
    source_type: str
    params: dict = field(default_factory=dict)
    credential_env: dict = field(default_factory=dict)
    markings: list = field(default_factory=list)
    description: str = ""

    def secret(self, key: str, default: str = "") -> str:
        """按引用从环境变量解析一个凭据（值绝不落在 Source 对象里）。"""
        if key not in self.credential_env:
            return default
        env_name = normalize_env_name(
            self.credential_env[key], field_name=f"credential_env[{key!r}]"
        )
        return os.environ.get(env_name, default)


class Connector(ABC):
    """某类源系统的集成器基类。"""
    source_type = "base"

    def __init__(self, source: Source):
        if not isinstance(source, Source):
            raise TypeError(f"source 必须是 Source，实际为 {type(source).__name__}")
        if self.source_type != "base" and source.source_type != self.source_type:
            raise ValueError(
                f"连接器类型 {self.source_type!r} 与 Source.source_type {source.source_type!r} 不匹配"
            )
        self.source = source

    @abstractmethod
    def test_connection(self) -> tuple:
        """返回 (ok: bool, message: str)。"""

    @abstractmethod
    def introspect(self) -> list:
        """自省源 schema，返回 list[DatasetDef]（表/列/类型/主键）。接真实客户库即用。"""

    @abstractmethod
    def read_table(self, name: str, limit: Optional[int] = None,
                   cursor_col: Optional[str] = None, since=None) -> tuple:
        """读一张表，返回 (columns: list[str], rows: list[tuple])。
        cursor_col + since 用于增量（对标 Palantir 的单调游标 `WHERE col > ?`）。"""

    def capabilities(self) -> dict:
        return {"snapshot": True, "incremental": False, "cdc": False}

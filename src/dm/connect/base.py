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
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SyncMode(str, Enum):
    SNAPSHOT = "snapshot"        # 全量替换（源不支持增量时）
    INCREMENTAL = "incremental"  # 单调游标增量（APPEND 风格）
    CDC = "cdc"                  # 流式变更捕获（我们由 Flink CDC 承担）


@dataclass
class ColumnDef:
    """自省得到的一列。"""
    name: str
    data_type: str               # 源系统原始类型（如 varchar / int4 / datetime）
    nullable: bool = True
    is_primary_key: bool = False


@dataclass
class DatasetDef:
    """自省得到的一张源表定义 —— 将落为一个 **raw 数据集**。"""
    name: str
    columns: list = field(default_factory=list)      # list[ColumnDef]
    primary_key: list = field(default_factory=list)   # 列名列表
    row_estimate: Optional[int] = None

    def col_names(self):
        return [c.name for c in self.columns]


@dataclass
class Source:
    """治理化的连接源。凭据不内联——`credential_env` 只存环境变量名。"""
    name: str
    source_type: str                                  # postgres / sqlserver / file
    params: dict = field(default_factory=dict)        # host/port/db/path 等（非敏感）
    credential_env: dict = field(default_factory=dict)  # {"password": "DM_SRC_PG_PASSWORD"}
    markings: list = field(default_factory=list)      # 源打标 → 传播到下游数据集
    description: str = ""

    def secret(self, key: str, default: str = "") -> str:
        """按引用从环境变量解析一个凭据（值绝不落在 Source 对象里）。"""
        env_name = self.credential_env.get(key)
        return os.environ.get(env_name, default) if env_name else default


class Connector(ABC):
    """某类源系统的集成器基类。"""
    source_type = "base"

    def __init__(self, source: Source):
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

"""连接器层（对标 Palantir Data Connection）。

- base：Source / Connector / DatasetDef / SyncMode（凭据引用不内联 + 源打标）
- postgres / sqlserver / file：三个具体连接器（PG 真实可用；U8 待真库；文件 CSV/Excel）
- catalog：源目录 + 连接器工厂

见 docs/palantir/01-数据连接层-Data-Connection.md。
"""
from dm.connect.base import ColumnDef, Connector, DatasetDef, Source, SyncMode
from dm.connect.catalog import get_connector, get_source, list_sources, SOURCES

__all__ = [
    "ColumnDef", "Connector", "DatasetDef", "Source", "SyncMode",
    "get_connector", "get_source", "list_sources", "SOURCES",
]

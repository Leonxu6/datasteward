"""源目录（Source Catalog）+ 连接器工厂。

登记治理化的连接源，并按 source_type 实例化对应连接器。对标 Palantir Data Connection
里"一个 Foundry 实例挂多个 Source"的形态。默认三源：PG 影子源（真实可用）、
用友 U8（待真库）、文件源。
"""
from dm.connect.base import Connector, Source
from dm.connect.file import FileConnector, default_file_source
from dm.connect.postgres import PostgresConnector, default_pg_source
from dm.connect.sqlserver import SqlServerConnector, default_u8_source

_CONNECTORS = {
    "postgres": PostgresConnector,
    "sqlserver": SqlServerConnector,
    "file": FileConnector,
}


def default_sources() -> dict:
    return {s.name: s for s in (default_pg_source(), default_u8_source(), default_file_source())}


# 进程级源目录（PoC：默认三源；真实部署可从配置/DB 加载）
SOURCES: dict = default_sources()


def list_sources() -> list:
    return list(SOURCES.values())


def get_source(name: str) -> Source:
    return SOURCES.get(name)


def get_connector(name_or_source) -> Connector:
    """按源名或 Source 对象返回连接器实例。"""
    src = get_source(name_or_source) if isinstance(name_or_source, str) else name_or_source
    if src is None:
        raise KeyError(f"未知源: {name_or_source}")
    cls = _CONNECTORS.get(src.source_type)
    if cls is None:
        raise KeyError(f"不支持的源类型: {src.source_type}")
    return cls(src)

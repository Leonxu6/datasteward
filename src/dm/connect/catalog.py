"""Source Catalog + connector factory.

默认登记 PostgreSQL、U8/SQL Server 与文件源；测试、插件或部署代码也可以显式注册
额外 Source。注册接口拒绝重复名称和未知连接器类型，避免静默覆盖已有生产配置。
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


def _normalize_source_name(name) -> str:
    if not isinstance(name, str):
        raise TypeError(f"源名称必须是字符串，实际为 {type(name).__name__}")
    if not name or name != name.strip():
        raise ValueError(f"源名称必须非空且不能包含首尾空白: {name!r}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        raise ValueError(f"源名称不能包含控制字符: {name!r}")
    return name


def _source_map(sources) -> dict[str, Source]:
    result: dict[str, Source] = {}
    for source in sources:
        if not isinstance(source, Source):
            raise TypeError(f"源目录成员必须是 Source，实际为 {type(source).__name__}")
        name = _normalize_source_name(source.name)
        if name in result:
            raise ValueError(f"重复源名称: {name}")
        if source.source_type not in _CONNECTORS:
            raise ValueError(f"不支持的源类型: {source.source_type}")
        result[name] = source
    return result


def default_sources() -> dict:
    return _source_map((default_pg_source(), default_u8_source(), default_file_source()))


SOURCES: dict[str, Source] = default_sources()


def list_sources() -> list:
    return list(SOURCES.values())


def get_source(name: str) -> Source | None:
    return SOURCES.get(_normalize_source_name(name))


def register_source(source: Source, *, replace: bool = False) -> Source:
    """Register one runtime source and return it; duplicates require explicit ``replace=True``."""
    if not isinstance(source, Source):
        raise TypeError(f"source 必须是 Source，实际为 {type(source).__name__}")
    if not isinstance(replace, bool):
        raise TypeError("replace 必须是布尔值")
    name = _normalize_source_name(source.name)
    if source.source_type not in _CONNECTORS:
        raise ValueError(f"不支持的源类型: {source.source_type}")
    if name in SOURCES and not replace:
        raise KeyError(f"源已存在: {name}")
    SOURCES[name] = source
    return source


def unregister_source(name: str) -> Source:
    """Remove one runtime source, returning the removed definition."""
    name = _normalize_source_name(name)
    try:
        return SOURCES.pop(name)
    except KeyError as exc:
        raise KeyError(f"未知源: {name}") from exc


def get_connector(name_or_source) -> Connector:
    """按源名或 Source 对象返回连接器实例。"""
    if isinstance(name_or_source, str):
        source = get_source(name_or_source)
    elif isinstance(name_or_source, Source):
        source = name_or_source
    else:
        raise TypeError(f"连接器参数必须是源名称或 Source，实际为 {type(name_or_source).__name__}")
    if source is None:
        raise KeyError(f"未知源: {name_or_source}")
    connector_cls = _CONNECTORS.get(source.source_type)
    if connector_cls is None:
        raise KeyError(f"不支持的源类型: {source.source_type}")
    return connector_cls(source)

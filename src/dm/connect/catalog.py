"""Source Catalog + connector factory.

Runtime registration is intentionally strict: source names are user-facing
identities, so names that differ only by case are rejected rather than becoming
platform- or UI-dependent aliases.
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
_MAX_SOURCE_NAME = 128


def _normalize_source_name(name) -> str:
    if not isinstance(name, str):
        raise TypeError(f"源名称必须是字符串，实际为 {type(name).__name__}")
    if not name or name != name.strip():
        raise ValueError(f"源名称必须非空且不能包含首尾空白: {name!r}")
    if len(name) > _MAX_SOURCE_NAME:
        raise ValueError(f"源名称不能超过 {_MAX_SOURCE_NAME} 个字符")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name):
        raise ValueError(f"源名称不能包含控制字符: {name!r}")
    return name


def _normalize_source_type(value) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"源类型必须是非空且无首尾空白的字符串: {value!r}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"源类型不能包含控制字符: {value!r}")
    if value not in _CONNECTORS:
        raise ValueError(f"不支持的源类型: {value}")
    return value


def _find_casefold_collision(name: str, names) -> str | None:
    folded = name.casefold()
    for existing in names:
        if existing != name and existing.casefold() == folded:
            return existing
    return None


def _source_map(sources) -> dict[str, Source]:
    if isinstance(sources, (str, bytes, bytearray, dict)):
        raise TypeError("源目录必须是 Source 集合")
    result: dict[str, Source] = {}
    for source in sources:
        if not isinstance(source, Source):
            raise TypeError(f"源目录成员必须是 Source，实际为 {type(source).__name__}")
        name = _normalize_source_name(source.name)
        if name in result:
            raise ValueError(f"重复源名称: {name}")
        collision = _find_casefold_collision(name, result)
        if collision:
            raise ValueError(f"源名称大小写冲突: {name} 与 {collision}")
        _normalize_source_type(source.source_type)
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
    _normalize_source_type(source.source_type)
    collision = _find_casefold_collision(name, SOURCES)
    if collision:
        raise ValueError(f"源名称大小写冲突: {name} 与 {collision}")
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
        _normalize_source_name(source.name)
        _normalize_source_type(source.source_type)
    else:
        raise TypeError(f"连接器参数必须是源名称或 Source，实际为 {type(name_or_source).__name__}")
    if source is None:
        raise KeyError(f"未知源: {name_or_source}")
    connector_cls = _CONNECTORS[source.source_type]
    return connector_cls(source)

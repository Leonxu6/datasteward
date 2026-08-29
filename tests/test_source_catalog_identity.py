import pytest

from dm.connect import catalog
from dm.connect.base import Source


def _source(name, source_type="file"):
    return Source(name=name, source_type=source_type)


def test_source_map_rejects_scalar_collections_and_casefold_collisions():
    for value in ("source", {"source": _source("source")}):
        with pytest.raises(TypeError):
            catalog._source_map(value)
    with pytest.raises(ValueError, match="大小写冲突"):
        catalog._source_map([_source("ERP"), _source("erp")])


def test_source_names_are_bounded_and_control_safe():
    for name in ("x" * 129, "erp\n"):
        with pytest.raises(ValueError):
            catalog._normalize_source_name(name)


def test_source_types_are_clean_and_supported():
    for source_type in (None, " file", "file\n", "oracle"):
        with pytest.raises(ValueError):
            catalog._normalize_source_type(source_type)
    assert catalog._normalize_source_type("file") == "file"


def test_register_source_rejects_casefold_aliases(monkeypatch):
    monkeypatch.setattr(catalog, "SOURCES", {"ERP": _source("ERP")})
    with pytest.raises(ValueError, match="大小写冲突"):
        catalog.register_source(_source("erp"))


def test_get_connector_validates_direct_source_objects(monkeypatch):
    monkeypatch.setitem(catalog._CONNECTORS, "file", lambda source: ("connector", source.name))
    assert catalog.get_connector(_source("docs", "file")) == ("connector", "docs")
    with pytest.raises(ValueError):
        catalog.get_connector(_source("docs", " file"))

import pytest

from dm.connect.base import Source
from dm.connect import catalog


def test_register_and_unregister_runtime_source(monkeypatch):
    monkeypatch.setattr(catalog, "SOURCES", {})
    source = Source(name="dropzone", source_type="file", params={"dir": "/tmp/drop"})

    registered = catalog.register_source(source)
    fetched = catalog.get_source("dropzone")
    removed = catalog.unregister_source("dropzone")

    assert registered == source and registered is not source
    assert fetched == source and fetched is not source and fetched is not registered
    assert removed == source and removed is not source
    registered.params["dir"] = "/tmp/changed"
    assert source.params["dir"] == "/tmp/drop"
    assert catalog.get_source("dropzone") is None


def test_register_rejects_duplicate_without_explicit_replace(monkeypatch):
    original = Source(name="dropzone", source_type="file")
    replacement = Source(name="dropzone", source_type="file", description="new")
    monkeypatch.setattr(catalog, "SOURCES", {"dropzone": original})
    with pytest.raises(KeyError, match="已存在"):
        catalog.register_source(replacement)

    registered = catalog.register_source(replacement, replace=True)
    assert registered == replacement and registered is not replacement
    assert catalog.SOURCES["dropzone"] == replacement
    assert catalog.SOURCES["dropzone"] is not replacement


def test_register_requires_boolean_replace_flag(monkeypatch):
    source = Source(name="dropzone", source_type="file")
    monkeypatch.setattr(catalog, "SOURCES", {"dropzone": source})
    for replace in (1, 0, "true", None):
        with pytest.raises(TypeError, match="replace"):
            catalog.register_source(source, replace=replace)  # type: ignore[arg-type]
    assert catalog.SOURCES["dropzone"] is source


def test_register_rejects_unknown_connector_type_and_invalid_name(monkeypatch):
    monkeypatch.setattr(catalog, "SOURCES", {})
    with pytest.raises(ValueError, match="不支持"):
        catalog.register_source(Source(name="custom", source_type="unknown"))
    for name in ("", " padded", "padded ", "bad\nname"):
        with pytest.raises(ValueError):
            catalog.register_source(Source(name=name, source_type="file"))


def test_unregister_unknown_source_has_clear_error(monkeypatch):
    monkeypatch.setattr(catalog, "SOURCES", {})
    with pytest.raises(KeyError, match="未知源"):
        catalog.unregister_source("missing")

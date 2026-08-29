from dm.connect import catalog
from dm.connect.base import Source


def _source(name="test-source"):
    return Source(
        name=name,
        source_type="file",
        params={"dir": "/tmp/data", "nested": {"mode": "safe"}},
        credential_env={"token": "TEST_TOKEN"},
        markings=["U8"],
    )


def test_register_source_isolates_caller_mutations(monkeypatch):
    monkeypatch.setattr(catalog, "SOURCES", {})
    source = _source()
    returned = catalog.register_source(source)
    source.params["nested"]["mode"] = "mutated"
    source.markings.append("PII")
    returned.params["dir"] = "/mutated"
    stored = catalog.get_source("test-source")
    assert stored.params == {"dir": "/tmp/data", "nested": {"mode": "safe"}}
    assert stored.markings == ["U8"]


def test_get_and_list_sources_return_defensive_copies(monkeypatch):
    monkeypatch.setattr(catalog, "SOURCES", {"test-source": _source()})
    fetched = catalog.get_source("test-source")
    listed = catalog.list_sources()[0]
    fetched.params["dir"] = "/changed"
    listed.credential_env["token"] = "OTHER_TOKEN"
    assert catalog.SOURCES["test-source"].params["dir"] == "/tmp/data"
    assert catalog.SOURCES["test-source"].credential_env["token"] == "TEST_TOKEN"


def test_unregister_returns_copy_without_leaking_removed_registry_object(monkeypatch):
    original = _source()
    monkeypatch.setattr(catalog, "SOURCES", {"test-source": original})
    removed = catalog.unregister_source("test-source")
    removed.params["dir"] = "/changed"
    assert original.params["dir"] == "/tmp/data"
    assert catalog.SOURCES == {}


def test_connector_from_source_receives_isolated_definition(monkeypatch):
    source = _source()
    connector = catalog.get_connector(source)
    source.params["dir"] = "/changed"
    assert connector.source.params["dir"] == "/tmp/data"

import pytest

from dm.security import model


def test_user_copies_attrs_instead_of_sharing_caller_mapping():
    attrs = {"warehouse_id": "W01"}
    user = model.User("alice", attrs=attrs)
    attrs["warehouse_id"] = "W02"
    assert user.attrs == {"warehouse_id": "W01"}


def test_user_rejects_malformed_identity_fields_and_attrs():
    for name in ("", " alice", "alice\n", None):
        with pytest.raises(ValueError):
            model.User(name)
    with pytest.raises(ValueError):
        model.User("alice", attrs=[])
    with pytest.raises(ValueError):
        model.User("alice", role=" warehouse")
    with pytest.raises(ValueError):
        model.User("alice", purpose="audit\n")


def test_column_markings_returns_a_defensive_copy(monkeypatch):
    monkeypatch.setitem(model.COLUMN_MARKINGS, ("orders", "price"), ["FIN"])
    markings = model.column_markings("orders", "price")
    markings.append("PII")
    assert model.COLUMN_MARKINGS[("orders", "price")] == ["FIN"]


def test_table_markings_returns_a_defensive_copy(monkeypatch):
    monkeypatch.setitem(model.TABLE_MARKINGS, "orders", ["FIN"])
    markings = model.table_markings("orders")
    markings.clear()
    assert model.TABLE_MARKINGS["orders"] == ["FIN"]


def test_marking_lookup_names_reject_control_or_padding():
    for table, column in ((" orders", "price"), ("orders", "price\n"), ("", "price")):
        with pytest.raises(ValueError):
            model.column_markings(table, column)

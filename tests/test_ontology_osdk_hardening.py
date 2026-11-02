from types import SimpleNamespace

import pytest

from dm.ontology import osdk
from dm.ontology.osdk import _row_to_obj, _row_to_raw, get_links, list_objects


@pytest.mark.parametrize("value", [True, False, 0, -1, 501, 1.5, "10", None])
def test_list_objects_rejects_invalid_limits_before_database_access(value):
    with pytest.raises(ValueError):
        list_objects("Material", limit=value)


@pytest.mark.parametrize("value", [True, False, 0, -1, 201, 1.5, "10", None])
def test_get_links_rejects_invalid_per_link_limits_before_database_access(value):
    with pytest.raises(ValueError):
        get_links("Material", "M001", per_link_limit=value)


@pytest.mark.parametrize("value", [3, [], "", " name", "name ", "name\n", "definitely_unknown"])
def test_list_objects_rejects_invalid_sort_properties_before_database_access(value):
    with pytest.raises(ValueError):
        list_objects("Material", order_by=value)


def _object_type_stub():
    return SimpleNamespace(
        api_name="Material",
        table="material",
        display_name="Material",
        primary_key=["id"],
        links=[],
        properties=[
            SimpleNamespace(api_name="id", column="id"),
            SimpleNamespace(api_name="name", column="name"),
        ],
        prop=lambda name: None,
    )


class _Cursor:
    description = [("id",), ("name",)]

    def __init__(self, rows):
        self.rows = rows
        self.fetch_sizes = []

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        return self.rows[:size]


class _Connection:
    def __init__(self, rows):
        self.cursor = _Cursor(rows)
        self.calls = []
        self.closed = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self.cursor

    def close(self):
        self.closed = True


def test_list_objects_enforces_limit_at_driver_boundary(monkeypatch):
    connection = _Connection([("M001", "one"), ("M002", "two"), ("M003", "three")])
    monkeypatch.setattr(osdk, "get_object_type", lambda _name: _object_type_stub())
    monkeypatch.setattr(osdk, "connect_ro", lambda: connection)

    with pytest.raises(RuntimeError, match="Material object listing exceeded its 2-row budget"):
        list_objects("Material", limit=2)

    assert connection.cursor.fetch_sizes == [3]
    assert connection.calls == [("SELECT * FROM `material` LIMIT 3", None)]
    assert connection.closed is True


def test_get_links_enforces_each_incoming_link_budget(monkeypatch):
    connection = _Connection([("C001", "one"), ("C002", "two"), ("C003", "three")])
    root = _object_type_stub()
    child = _object_type_stub()
    child.api_name = "Child"
    child.table = "child"
    link = SimpleNamespace(
        api_name="material",
        from_object="Child",
        from_property="material_id",
        display_name="Child to material",
    )
    monkeypatch.setattr(osdk, "_fetch_row", lambda _ot, _pk: {"id": "M001", "name": "root"})
    monkeypatch.setattr(osdk, "get_object_type", lambda name: child if name == "Child" else root)
    monkeypatch.setattr(osdk, "incoming_links", lambda _name: [link])
    monkeypatch.setattr(osdk, "connect_ro", lambda: connection)

    with pytest.raises(RuntimeError, match="Child.material incoming link exceeded its 2-row budget"):
        get_links("Material", "M001", per_link_limit=2)

    assert connection.cursor.fetch_sizes == [3]
    assert connection.calls == [
        ("SELECT * FROM `child` WHERE `material_id` = %s LIMIT 3", ("M001",))
    ]
    assert connection.closed is True


def test_row_to_obj_rejects_mismatched_row_lengths():
    with pytest.raises(ValueError, match="row length"):
        _row_to_obj(_object_type_stub(), ("M001",), ["id", "name"])


def test_row_to_obj_rejects_duplicate_columns():
    with pytest.raises(ValueError, match="duplicate"):
        _row_to_obj(_object_type_stub(), ("M001", "copy"), ["id", "id"])


@pytest.mark.parametrize("columns", [["id", ""], ["id", 3]])
def test_row_to_obj_rejects_invalid_column_labels(columns):
    with pytest.raises(ValueError, match="non-empty strings"):
        _row_to_obj(_object_type_stub(), ("M001", "name"), columns)


@pytest.mark.parametrize(
    ("row", "columns", "message"),
    [
        (object(), ["id"], "sized sequences"),
        (("M001",), ["id", "name"], "row length"),
        (("M001", "copy"), ["id", "id"], "duplicate"),
        (("M001", "name"), ["id", ""], "non-empty strings"),
    ],
)
def test_row_to_raw_rejects_malformed_single_object_rows(row, columns, message):
    with pytest.raises(ValueError, match=message):
        _row_to_raw(row, columns)


def test_row_to_raw_preserves_valid_single_object_rows():
    assert _row_to_raw(("M001", "Bolt"), ["id", "name"]) == {"id": "M001", "name": "Bolt"}

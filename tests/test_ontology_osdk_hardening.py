from types import SimpleNamespace

import pytest

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
        properties=[
            SimpleNamespace(api_name="id", column="id"),
            SimpleNamespace(api_name="name", column="name"),
        ]
    )


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

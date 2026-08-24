from types import SimpleNamespace

import pytest

from dm.ontology.osdk import _row_to_obj, get_links, list_objects


@pytest.mark.parametrize("value", [True, False, 0, -1, 501, 1.5, "10", None])
def test_list_objects_rejects_invalid_limits_before_database_access(value):
    with pytest.raises(ValueError):
        list_objects("Material", limit=value)


@pytest.mark.parametrize("value", [True, False, 0, -1, 201, 1.5, "10", None])
def test_get_links_rejects_invalid_per_link_limits_before_database_access(value):
    with pytest.raises(ValueError):
        get_links("Material", "M001", per_link_limit=value)


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

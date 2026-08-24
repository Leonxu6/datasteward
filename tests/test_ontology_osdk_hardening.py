import pytest

from dm.ontology.osdk import get_links, list_objects


@pytest.mark.parametrize("value", [True, False, 0, -1, 501, 1.5, "10", None])
def test_list_objects_rejects_invalid_limits_before_database_access(value):
    with pytest.raises(ValueError):
        list_objects("Material", limit=value)


@pytest.mark.parametrize("value", [True, False, 0, -1, 201, 1.5, "10", None])
def test_get_links_rejects_invalid_per_link_limits_before_database_access(value):
    with pytest.raises(ValueError):
        get_links("Material", "M001", per_link_limit=value)

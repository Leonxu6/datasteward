import pytest

from dm.ontology.model import get_object_type, incoming_links, to_camel, to_pascal


@pytest.mark.parametrize("value", [None, 3, [], "", " material", "material ", "material\n"])
def test_get_object_type_rejects_invalid_lookup_names(value):
    with pytest.raises(ValueError):
        get_object_type(value)


@pytest.mark.parametrize("value", [None, 3, [], "", " purchase_order", "purchase_order ", "a\tb"])
def test_to_pascal_rejects_invalid_source_names(value):
    with pytest.raises(ValueError):
        to_pascal(value)


@pytest.mark.parametrize("value", [None, 3, [], "", " unit_price", "unit_price ", "a\nb"])
def test_to_camel_rejects_invalid_source_names(value):
    with pytest.raises(ValueError):
        to_camel(value)


def test_name_conversion_stays_deterministic():
    assert to_pascal("purchase_order") == "PurchaseOrder"
    assert to_camel("unit_price") == "unitPrice"


def test_unknown_clean_object_type_still_returns_none():
    assert get_object_type("DefinitelyUnknown") is None
    assert incoming_links("DefinitelyUnknown") == []

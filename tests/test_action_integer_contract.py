"""Action parameter validation must honor the declared Integer schema."""

import pytest

from dm.ontology import actions


@pytest.mark.parametrize("value", [True, False, 1.5, "1", None])
def test_safety_stock_rejects_values_that_only_int_coercion_accepts(value):
    assert actions._validate(
        "adjust_safety_stock", {"material_id": "M0001", "new_value": value}
    ) == "new_value 必须为整数"


@pytest.mark.parametrize("action, identity", [
    ("create_purchase_requisition", {"material_id": "M0001", "supplier_id": "S0001"}),
    ("create_delivery", {"so_id": "SO0001"}),
])
@pytest.mark.parametrize("value", [True, False, 1.5, "2", None])
def test_quantity_actions_reject_values_that_only_int_coercion_accepts(action, identity, value):
    assert actions._validate(action, {**identity, "qty": value}) == "qty 必须为整数"


@pytest.mark.parametrize("value", [0, 7])
def test_safety_stock_keeps_valid_integer_boundaries(value):
    assert actions._validate(
        "adjust_safety_stock", {"material_id": "M0001", "new_value": value}
    ) is None


@pytest.mark.parametrize("action, identity", [
    ("create_purchase_requisition", {"material_id": "M0001", "supplier_id": "S0001"}),
    ("create_delivery", {"so_id": "SO0001"}),
])
def test_quantity_actions_keep_positive_integers(action, identity):
    assert actions._validate(action, {**identity, "qty": 2}) is None

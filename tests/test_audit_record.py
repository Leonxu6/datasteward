from datetime import datetime
from decimal import Decimal

from dm.tools.audit_record import elapsed_ms, join_labels, safe_json


def test_safe_json_serializes_datetime_and_decimal_values():
    text = safe_json({"at": datetime(2026, 8, 21, 17, 0), "amount": Decimal("12.34")})
    assert '"amount": "12.34"' in text
    assert '"at": "2026-08-21 17:00:00"' in text


def test_safe_json_falls_back_for_recursive_values():
    value = []
    value.append(value)
    text = safe_json(value)
    assert "serialization_error" in text


def test_join_labels_normalizes_scalars_and_drops_empty_values():
    assert join_labels(["orders", " ", 7, None]) == "orders,7,None"
    assert join_labels(None) == ""


def test_elapsed_ms_is_nonnegative_and_handles_bad_inputs():
    assert elapsed_ms(10.0, 10.125) == 125
    assert elapsed_ms(10.0, 9.0) == 0
    assert elapsed_ms("bad", 12.0) == 0

from decimal import Decimal

from dm.connect.u8_mapping import _norm


def test_decimal_values_are_not_coerced_to_binary_float():
    value = Decimal("1234567890.1234")
    normalized = _norm(value)
    assert normalized is value
    assert isinstance(normalized, Decimal)
    assert str(normalized) == "1234567890.1234"

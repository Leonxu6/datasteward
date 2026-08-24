import pytest

import dm.llm as llm


def test_finite_number_normalizes_huge_integer_overflow():
    with pytest.raises(ValueError, match="timeout"):
        llm._finite_number(10**10000, field_name="timeout")


def test_positive_number_normalizes_huge_integer_overflow():
    with pytest.raises(ValueError, match="timeout"):
        llm._positive_number(10**10000, field_name="timeout")

from decimal import Decimal

import pytest

from dm.eval.grading import grade_numeric
from dm.eval.schema import EvalCaseError


def test_numeric_grader_preserves_decimal_precision():
    expected = Decimal("12345678901234567890.1250")
    ok, rendered = grade_numeric([(expected,)], "value=12345678901234567890.125")
    assert ok is True
    assert rendered == "12345678901234567890.125"


def test_numeric_grader_rejects_non_finite_decimals():
    with pytest.raises(EvalCaseError, match="finite"):
        grade_numeric([(Decimal("NaN"),)], "NaN")

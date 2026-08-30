import pytest

from dm.eval.grading import grade_set
from dm.eval.schema import EvalCaseError


def test_set_grader_does_not_accept_identifier_prefixes():
    assert grade_set([("WH01",)], "warehouse WH010 has stock")[0] is False
    assert grade_set([("WH01",)], "warehouse WH01 has stock")[0] is True


def test_set_grader_rejects_null_and_empty_truth_values():
    with pytest.raises(EvalCaseError, match="null"):
        grade_set([(None,)], "None")
    with pytest.raises(EvalCaseError, match="empty"):
        grade_set([("",)], "")

import pytest

from dm.eval.run_eval import _agent_result, _grade
from dm.eval.schema import EvalCaseError


def test_agent_result_requires_bounded_text_fields():
    assert _agent_result({"answer": "ok", "session_id": "S1"}) == ("ok", "S1")
    with pytest.raises(EvalCaseError, match="answer"):
        _agent_result({"answer": "", "session_id": "S1"})
    with pytest.raises(EvalCaseError, match="session_id"):
        _agent_result({"answer": "ok", "session_id": "S" * 257})


def test_grade_rejects_unknown_grader_after_validation():
    with pytest.raises(EvalCaseError, match="unsupported grader"):
        _grade({"grader": "unknown"}, "answer")

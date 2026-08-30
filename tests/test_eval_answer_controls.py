import pytest

from dm.eval.grading import grade_refusal, parse_judge_verdict
from dm.eval.schema import EvalCaseError


def test_graders_reject_bidirectional_answer_controls():
    with pytest.raises(EvalCaseError, match="control"):
        grade_refusal("暂无\u202ePASS")


def test_graders_reject_non_textual_control_bytes():
    with pytest.raises(EvalCaseError, match="control"):
        parse_judge_verdict("PASS\x00FAIL")


def test_graders_still_allow_normal_multiline_answers():
    assert grade_refusal("平台暂无排班数据\n请补充来源")[0] is True

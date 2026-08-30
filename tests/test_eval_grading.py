import pytest

from dm.eval.grading import (
    compute_facts,
    grade_contains,
    grade_numeric,
    grade_refusal,
    grade_set,
    parse_judge_verdict,
)
from dm.eval.schema import EvalCaseError


def test_numeric_grader_requires_one_finite_scalar():
    assert grade_numeric([(1200,)], "Total is 1,200 units") == (True, "1200")
    with pytest.raises(EvalCaseError, match="exactly one row"):
        grade_numeric([], "0")
    with pytest.raises(EvalCaseError, match="finite"):
        grade_numeric([(float("inf"),)], "inf")


def test_numeric_grader_does_not_match_larger_decimal_tokens():
    assert grade_numeric([(12,)], "value=12.5")[0] is False


def test_set_grader_deduplicates_and_validates_row_shape():
    ok, expected = grade_set([("WH01",), ("WH01",), ("WH02",)], "WH02 and WH01")
    assert ok is True
    assert expected == "{WH01, WH02}"
    with pytest.raises(EvalCaseError, match="one column"):
        grade_set([("WH01", "extra")], "WH01")


def test_refusal_grader_requires_text():
    assert grade_refusal("平台暂无排班数据")[0] is True
    with pytest.raises(EvalCaseError, match="string"):
        grade_refusal(None)


def test_contains_grader_collapses_unicode_whitespace():
    ok, _ = grade_contains(["逾期 每日0.5%", "质保12个月"], "逾期\n每日0.5%，质保　12个月")
    assert ok is True


def test_compute_facts_redacts_backend_exceptions():
    def broken_query(sql):
        raise RuntimeError("postgres://user:secret@example.internal")

    rendered = compute_facts([{"label": "inventory", "sql": "SELECT 1"}], broken_query)
    assert rendered == "inventory=(unavailable)"
    assert "secret" not in rendered


def test_parse_judge_verdict_rejects_substrings_and_conflicts():
    assert parse_judge_verdict("PASS") == (True, "PASS")
    assert parse_judge_verdict("BYPASS") == (False, "INVALID")
    assert parse_judge_verdict("PASS then FAIL") == (False, "FAIL")

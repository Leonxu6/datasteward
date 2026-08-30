import pytest

from dm.eval.schema import EvalCaseError, validate_case


def _case(sql):
    return {
        "id": "C1",
        "category": "direct",
        "question": "How many rows?",
        "grader": "numeric",
        "truth_sql": sql,
    }


def test_truth_sql_accepts_select_and_cte_queries():
    assert validate_case(_case("SELECT COUNT(*) FROM material"))["truth_sql"].startswith("SELECT")
    assert validate_case(_case("WITH x AS (SELECT 1) SELECT * FROM x"))["truth_sql"].startswith("WITH")


def test_truth_sql_rejects_mutation_and_multiple_statements():
    with pytest.raises(EvalCaseError, match="read-only"):
        validate_case(_case("DELETE FROM material"))
    with pytest.raises(EvalCaseError, match="one statement"):
        validate_case(_case("SELECT 1; SELECT 2"))


def test_truth_facts_use_the_same_read_only_contract():
    case = {
        "id": "C2",
        "category": "multistep",
        "question": "Explain",
        "grader": "llm_judge",
        "truth_facts": [{"label": "danger", "sql": "UPDATE material SET name='x'"}],
    }
    with pytest.raises(EvalCaseError, match="read-only"):
        validate_case(case)

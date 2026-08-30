import pytest

from dm.eval.schema import EvalCaseError, validate_case, validate_cases


def _numeric_case(**overrides):
    case = {
        "id": "C1",
        "category": "direct",
        "question": "How many rows are present?",
        "grader": "numeric",
        "truth_sql": "SELECT COUNT(*) FROM material",
    }
    case.update(overrides)
    return case


def test_validate_cases_returns_defensive_validated_copies():
    original = _numeric_case()
    cases = validate_cases([original])

    assert cases[0] is not original
    assert cases[0]["id"] == "C1"


def test_validate_cases_rejects_duplicate_ids():
    with pytest.raises(EvalCaseError, match="duplicate eval case id"):
        validate_cases([_numeric_case(), _numeric_case(question="Another question")])


def test_validate_case_rejects_unknown_graders():
    with pytest.raises(EvalCaseError, match="unsupported"):
        validate_case(_numeric_case(grader="magic"))


def test_validate_case_requires_truth_sql_for_deterministic_graders():
    case = _numeric_case()
    case.pop("truth_sql")
    with pytest.raises(EvalCaseError, match="truth_sql"):
        validate_case(case)


def test_validate_case_requires_contains_needles():
    with pytest.raises(EvalCaseError, match="expected_contains"):
        validate_case({
            "id": "C2",
            "category": "rag",
            "question": "Find the contract fact",
            "grader": "contains",
            "expected_contains": [],
        })


def test_validate_case_rejects_bidirectional_controls():
    with pytest.raises(EvalCaseError, match="control"):
        validate_case(_numeric_case(question="safe\u202eunsafe"))


def test_validate_truth_facts_are_copied_and_bounded():
    case = {
        "id": "C3",
        "category": "multistep",
        "question": "Explain the result",
        "grader": "llm_judge",
        "expected": "A supported answer",
        "truth_facts": [{"label": "row count", "sql": "SELECT COUNT(*) FROM material"}],
    }

    validated = validate_case(case)
    assert validated["truth_facts"] == ({"label": "row count", "sql": "SELECT COUNT(*) FROM material"},)

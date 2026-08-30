import pytest

from dm.eval.schema import EvalCaseError
from dm.eval.yaml_loader import load_eval_cases


VALID = """\
- id: C1
  category: direct
  question: How many rows?
  grader: numeric
  truth_sql: SELECT COUNT(*) FROM material
"""


def test_load_eval_cases_validates_yaml_and_schema():
    cases = load_eval_cases(VALID)
    assert cases[0]["id"] == "C1"


def test_load_eval_cases_rejects_duplicate_yaml_keys():
    duplicate = VALID.replace("  category: direct\n", "  category: direct\n  category: join\n")
    with pytest.raises(EvalCaseError, match="duplicate YAML key"):
        load_eval_cases(duplicate)


def test_load_eval_cases_normalizes_parser_errors():
    with pytest.raises(EvalCaseError, match="YAML is invalid"):
        load_eval_cases("- [unterminated")

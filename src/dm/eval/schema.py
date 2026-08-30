"""Validation helpers for repository eval cases.

Keep the evaluator strict at the file boundary so malformed cases fail before
an agent, warehouse, or LLM call can create an expensive or misleading run.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

_ALLOWED_GRADERS = frozenset({"numeric", "set", "refusal", "contains", "llm_judge"})
_MAX_CASES = 1_000
_MAX_TEXT = 20_000
_BIDI_CONTROLS = frozenset(chr(code) for code in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))


class EvalCaseError(ValueError):
    """Raised when an eval case does not satisfy the repository contract."""


def _text(value: object, *, field: str, max_length: int = _MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise EvalCaseError(f"{field} must be a string")
    if not value:
        raise EvalCaseError(f"{field} must not be empty")
    if value != value.strip():
        raise EvalCaseError(f"{field} must not have surrounding whitespace")
    if len(value) > max_length:
        raise EvalCaseError(f"{field} is too long")
    if any((ord(ch) < 32 and ch not in "\n\t") or ch in _BIDI_CONTROLS for ch in value):
        raise EvalCaseError(f"{field} contains unsafe control characters")
    return value


def _truth_sql(value: object, *, field: str) -> str:
    sql = _text(value, field=field)
    first = sql.lstrip().split(None, 1)[0].upper() if sql.lstrip() else ""
    if first not in {"SELECT", "WITH"}:
        raise EvalCaseError(f"{field} must be a read-only SELECT or WITH query")
    if ";" in sql:
        raise EvalCaseError(f"{field} must contain exactly one statement")
    return sql


def _string_list(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise EvalCaseError(f"{field} must be a sequence of strings")
    items = tuple(_text(item, field=f"{field} item", max_length=2_000) for item in value)
    if not items:
        raise EvalCaseError(f"{field} must not be empty")
    if len(items) > 100:
        raise EvalCaseError(f"{field} has too many items")
    return items


def _truth_facts(value: object) -> tuple[dict[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise EvalCaseError("truth_facts must be a sequence")
    if len(value) > 100:
        raise EvalCaseError("truth_facts has too many items")
    facts: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise EvalCaseError(f"truth_facts[{index}] must be a mapping")
        facts.append({
            "label": _text(item.get("label"), field=f"truth_facts[{index}].label", max_length=500),
            "sql": _truth_sql(item.get("sql"), field=f"truth_facts[{index}].sql"),
        })
    return tuple(facts)


def validate_case(case: object) -> dict[str, object]:
    """Return a defensive, validated copy of one eval case."""
    if not isinstance(case, Mapping):
        raise EvalCaseError("eval case must be a mapping")

    case_id = _text(case.get("id"), field="id", max_length=64)
    category = _text(case.get("category"), field=f"{case_id}.category", max_length=64)
    question = _text(case.get("question"), field=f"{case_id}.question", max_length=8_000)
    grader = _text(case.get("grader"), field=f"{case_id}.grader", max_length=32)
    if grader not in _ALLOWED_GRADERS:
        raise EvalCaseError(f"{case_id}.grader is unsupported: {grader}")

    normalized: dict[str, object] = dict(case)
    normalized.update(id=case_id, category=category, question=question, grader=grader)

    if grader in {"numeric", "set"}:
        normalized["truth_sql"] = _truth_sql(case.get("truth_sql"), field=f"{case_id}.truth_sql")
    elif grader == "contains":
        normalized["expected_contains"] = _string_list(
            case.get("expected_contains"), field=f"{case_id}.expected_contains"
        )

    if "expected" in case:
        normalized["expected"] = _text(case.get("expected"), field=f"{case_id}.expected")
    if "role" in case:
        normalized["role"] = _text(case.get("role"), field=f"{case_id}.role", max_length=128)
    if "purpose" in case:
        normalized["purpose"] = _text(case.get("purpose"), field=f"{case_id}.purpose", max_length=256)

    facts = _truth_facts(case.get("truth_facts"))
    if facts:
        normalized["truth_facts"] = facts
    elif "truth_facts" in normalized:
        normalized["truth_facts"] = ()
    return normalized


def validate_cases(raw: object) -> tuple[dict[str, object], ...]:
    """Validate a complete eval file and reject duplicate case identities."""
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        raise EvalCaseError("eval set must be a sequence")
    if not raw:
        raise EvalCaseError("eval set must not be empty")
    if len(raw) > _MAX_CASES:
        raise EvalCaseError(f"eval set must contain at most {_MAX_CASES} cases")

    cases = tuple(validate_case(case) for case in raw)
    seen: set[str] = set()
    for case in cases:
        case_id = str(case["id"])
        if case_id in seen:
            raise EvalCaseError(f"duplicate eval case id: {case_id}")
        seen.add(case_id)
    return cases

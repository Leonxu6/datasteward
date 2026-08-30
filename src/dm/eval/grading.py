"""Deterministic and LLM-backed grading primitives for eval runs."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from numbers import Real

from dm.eval.schema import EvalCaseError

REFUSAL_HINTS = (
    "暂无", "没有该", "无法", "不在", "没有相关", "缺少", "未包含", "查不到",
    "无此", "不包含", "没有排班", "没有产能", "未提及", "未规定", "没有规定",
    "未说明", "未注明", "未提到",
)
_MAX_ANSWER = 100_000
_MAX_FACTS = 100
_MAX_FACT_TEXT = 2_000
_IDENTIFIER_VALUE = re.compile(r"^[A-Za-z0-9_.-]+$")
_BIDI_CONTROL = re.compile("[\u202a-\u202e\u2066-\u2069]")
_UNSAFE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _answer_text(answer: object) -> str:
    if not isinstance(answer, str):
        raise EvalCaseError("grader answer must be a string")
    if len(answer) > _MAX_ANSWER:
        raise EvalCaseError("grader answer is too long")
    if _BIDI_CONTROL.search(answer) or _UNSAFE_CONTROL.search(answer):
        raise EvalCaseError("grader answer contains unsafe control characters")
    return answer


def _scalar_truth(rows: object) -> object:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise EvalCaseError("truth query must return a sequence")
    if len(rows) != 1:
        raise EvalCaseError("truth query must return exactly one row")
    row = rows[0]
    if not isinstance(row, Sequence) or isinstance(row, (str, bytes, bytearray)) or len(row) != 1:
        raise EvalCaseError("truth query must return exactly one column")
    return row[0]


def _render_numeric(value: object) -> str:
    if isinstance(value, bool):
        raise EvalCaseError("numeric truth value must be a real number")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise EvalCaseError("numeric truth value must be finite")
        integral = value.to_integral_value()
        return str(integral) if value == integral else format(value.normalize(), "f")
    if not isinstance(value, Real):
        raise EvalCaseError("numeric truth value must be a real number")
    number = float(value)
    if not math.isfinite(number):
        raise EvalCaseError("numeric truth value must be finite")
    if number.is_integer():
        return str(int(number))
    return format(number, ".15g")


def grade_numeric(rows: object, answer: object) -> tuple[bool, str]:
    expected = _render_numeric(_scalar_truth(rows))
    normalized = _answer_text(answer).replace(",", "")
    found = re.search(r"(?<![\d.])" + re.escape(expected) + r"(?![\d.])", normalized) is not None
    return found, expected


def _answer_contains_set_value(answer: str, value: str) -> bool:
    if _IDENTIFIER_VALUE.fullmatch(value):
        pattern = r"(?<![A-Za-z0-9_.-])" + re.escape(value) + r"(?![A-Za-z0-9_.-])"
        return re.search(pattern, answer) is not None
    return value in answer


def grade_set(rows: object, answer: object) -> tuple[bool, str]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise EvalCaseError("set truth query must return a sequence")
    items: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes, bytearray)) or len(row) != 1:
            raise EvalCaseError("set truth query rows must contain exactly one column")
        if row[0] is None:
            raise EvalCaseError("set truth query values must not be null")
        text = str(row[0])
        if not text:
            raise EvalCaseError("set truth query values must not be empty")
        if text not in seen:
            seen.add(text)
            items.append(text)
    haystack = _answer_text(answer)
    missing = [item for item in items if not _answer_contains_set_value(haystack, item)]
    return not missing, "{" + ", ".join(items) + "}"


def grade_refusal(answer: object) -> tuple[bool, str]:
    text = _answer_text(answer)
    return any(hint in text for hint in REFUSAL_HINTS), "正确拒答（无此数据）"


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", "", text, flags=re.UNICODE).replace("　", "")


def grade_contains(needles: object, answer: object) -> tuple[bool, str]:
    if not isinstance(needles, Sequence) or isinstance(needles, (str, bytes, bytearray)):
        raise EvalCaseError("expected_contains must be a sequence")
    if not needles:
        raise EvalCaseError("expected_contains must not be empty")
    normalized_needles: list[str] = []
    for needle in needles:
        if not isinstance(needle, str) or not needle:
            raise EvalCaseError("expected_contains values must be non-empty strings")
        normalized_needles.append(_collapse_whitespace(needle))
    norm = _collapse_whitespace(_answer_text(answer))
    missing = [needle for needle in normalized_needles if needle not in norm]
    missing_raw = [str(raw) for raw, needle in zip(needles, normalized_needles) if needle not in norm]
    exp = "需含: " + "、".join(str(n) for n in needles)
    if missing:
        exp += f"（缺: {'、'.join(missing_raw)}）"
    return not missing, exp


def compute_facts(items: object, truth_query) -> str:
    if items is None:
        return ""
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise EvalCaseError("truth_facts must be a sequence")
    if len(items) > _MAX_FACTS:
        raise EvalCaseError("truth_facts has too many items")
    out: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise EvalCaseError(f"truth_facts[{index}] must be a mapping")
        label, sql = item.get("label"), item.get("sql")
        if not isinstance(label, str) or not label or len(label) > 500:
            raise EvalCaseError(f"truth_facts[{index}].label is invalid")
        if not isinstance(sql, str) or not sql or len(sql) > 20_000:
            raise EvalCaseError(f"truth_facts[{index}].sql is invalid")
        try:
            value = _scalar_truth(truth_query(sql))
            rendered = str(value)
            if len(rendered) > _MAX_FACT_TEXT:
                rendered = rendered[:_MAX_FACT_TEXT] + "…"
            out.append(f"{label}={rendered}")
        except Exception:
            out.append(f"{label}=(unavailable)")
    return "；".join(out)


def parse_judge_verdict(output: object) -> tuple[bool, str]:
    text = _answer_text(output).strip().upper()
    tokens = re.findall(r"\b(?:PASS|FAIL)\b", text)
    verdict = tokens[-1] if tokens else ""
    if verdict == "PASS" and "FAIL" not in tokens:
        return True, "PASS"
    if verdict == "FAIL" or "FAIL" in tokens:
        return False, "FAIL"
    return False, "INVALID"

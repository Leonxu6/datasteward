"""Pure helpers for deterministic, bounded health-alert rendering."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

_MAX_FAILURES = 100
_MAX_ID = 64
_MAX_MESSAGE = 500
_MAX_RENDERED = 8
_BIDI = re.compile("[\u202a-\u202e\u2066-\u2069]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: object, *, fallback: str, limit: int) -> str:
    text = value if isinstance(value, str) else str(value) if value is not None else fallback
    text = _BIDI.sub("", _CONTROL.sub("", text)).strip()
    if not text:
        text = fallback
    return text[:limit]


def normalize_failures(summary: object) -> tuple[dict[str, str], ...]:
    if not isinstance(summary, Mapping):
        return ()
    results = summary.get("results", ())
    if not isinstance(results, Sequence) or isinstance(results, (str, bytes, bytearray)):
        return ()
    failures: list[dict[str, str]] = []
    for row in results:
        if not isinstance(row, Mapping) or row.get("status") != "fail":
            continue
        failures.append({
            "id": _clean(row.get("id"), fallback="?", limit=_MAX_ID),
            "message": _clean(row.get("message"), fallback="检查失败", limit=_MAX_MESSAGE),
        })
        if len(failures) >= _MAX_FAILURES:
            break
    failures.sort(key=lambda item: item["id"])
    return tuple(failures)


def failure_cursor(failures: Sequence[Mapping[str, str]]) -> str:
    ids = sorted({str(item.get("id", "?")) for item in failures})
    return json.dumps(ids, ensure_ascii=False, separators=(",", ":"))


def render_failure_alert(failures: Sequence[Mapping[str, str]]) -> str:
    lines = [f"🚨 数据健康告警（{len(failures)} 项 fail）："]
    for item in failures[:_MAX_RENDERED]:
        lines.append(f"· [{item.get('id', '?')}] {item.get('message', '检查失败')}")
    omitted = len(failures) - _MAX_RENDERED
    if omitted > 0:
        lines.append(f"· 另有 {omitted} 项失败未展开")
    lines.append("详见管理台「数据健康」页")
    return "\n".join(lines)

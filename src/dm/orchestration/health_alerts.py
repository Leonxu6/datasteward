"""Pure helpers for deterministic, bounded health-alert rendering."""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence

_MAX_RESULTS = 1_000
_MAX_FAILURES = 100
_MAX_ID = 64
_MAX_MESSAGE = 500
_MAX_RENDERED = 8
_BIDI = re.compile("[\u202a-\u202e\u2066-\u2069]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ALLOWED_STATUS = frozenset({"ok", "warn", "fail"})


class HealthAlertInputError(ValueError):
    """Raised when the health-check summary cannot be trusted."""


def _clean(value: object, *, fallback: str, limit: int) -> str:
    text = value if isinstance(value, str) else str(value) if value is not None else fallback
    text = _BIDI.sub("", _CONTROL.sub("", text)).strip()
    if not text:
        text = fallback
    return text[:limit]


def normalize_failures(summary: object) -> tuple[dict[str, str], ...]:
    if not isinstance(summary, Mapping):
        raise HealthAlertInputError("health summary must be a mapping")
    results = summary.get("results")
    if not isinstance(results, Sequence) or isinstance(results, (str, bytes, bytearray)):
        raise HealthAlertInputError("health summary results must be a sequence")
    if len(results) > _MAX_RESULTS:
        raise HealthAlertInputError(f"health summary has more than {_MAX_RESULTS} results")
    failures: list[dict[str, str]] = []
    healthy_ids: set[str] = set()
    failure_ids: set[str] = set()
    for index, row in enumerate(results):
        if not isinstance(row, Mapping):
            raise HealthAlertInputError(f"health result {index} must be a mapping")
        status = row.get("status")
        if status not in _ALLOWED_STATUS:
            raise HealthAlertInputError(f"health result {index} has an invalid status")

        raw_id = row.get("id")
        if status != "fail":
            if raw_id is not None:
                check_id = _clean(raw_id, fallback="?", limit=_MAX_ID)
                if check_id in failure_ids:
                    raise HealthAlertInputError(f"duplicate health result id: {check_id}")
                healthy_ids.add(check_id)
            continue

        check_id = _clean(raw_id, fallback="?", limit=_MAX_ID)
        if check_id in healthy_ids or check_id in failure_ids:
            raise HealthAlertInputError(f"duplicate health result id: {check_id}")
        failure_ids.add(check_id)
        failures.append({
            "id": check_id,
            "message": _clean(row.get("message"), fallback="检查失败", limit=_MAX_MESSAGE),
        })
        if len(failures) >= _MAX_FAILURES:
            break
    failures.sort(key=lambda item: item["id"])
    return tuple(failures)


def failure_cursor(failures: Sequence[Mapping[str, str]]) -> str:
    """Hash messages so changed failure details trigger a new alert without leaking them."""
    entries = []
    for item in failures:
        check_id = str(item.get("id", "?"))
        message = str(item.get("message", ""))
        digest = hashlib.sha256(message.encode("utf-8")).hexdigest()[:16]
        entries.append((check_id, digest))
    entries = sorted(set(entries))
    return json.dumps(entries, ensure_ascii=False, separators=(",", ":"))


def render_failure_alert(failures: Sequence[Mapping[str, str]]) -> str:
    lines = [f"🚨 数据健康告警（{len(failures)} 项 fail）："]
    for item in failures[:_MAX_RENDERED]:
        lines.append(f"· [{item.get('id', '?')}] {item.get('message', '检查失败')}")
    omitted = len(failures) - _MAX_RENDERED
    if omitted > 0:
        lines.append(f"· 另有 {omitted} 项失败未展开")
    lines.append("详见管理台「数据健康」页")
    return "\n".join(lines)

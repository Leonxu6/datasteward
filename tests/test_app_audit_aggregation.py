import math

from dm.app.data import agg_audit


def test_audit_aggregation_requires_explicit_boolean_success():
    rows = [
        {"id": "ok", "ok": True},
        {"id": "failed", "ok": False},
        {"id": "string", "ok": "false"},
        {"id": "integer", "ok": 1},
        {"id": "missing"},
    ]

    result = agg_audit(rows)

    assert result["ok"] == 1
    assert result["fail"] == 4
    assert result["success_rate"] == 20
    assert [row["id"] for row in result["failures"]] == [
        "missing",
        "integer",
        "string",
        "failed",
    ]


def test_audit_aggregation_ignores_invalid_duration_values():
    rows = [
        {"duration_ms": 0},
        {"duration_ms": 12.5},
        {"duration_ms": True},
        {"duration_ms": -1},
        {"duration_ms": math.nan},
        {"duration_ms": math.inf},
        {"duration_ms": "9"},
    ]

    result = agg_audit(rows)

    assert result["durations"] == [0, 12.5]
    assert result["avg_ms"] == 6


def test_audit_aggregation_averages_large_finite_durations_without_overflow():
    result = agg_audit([{"duration_ms": 1e308}, {"duration_ms": 1e308}])

    assert result["avg_ms"] == round(1e308)

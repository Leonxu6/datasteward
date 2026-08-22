from datetime import datetime

import pytest

from dm.health import checks


def _freshness_check():
    return {
        "id": "freshness_test",
        "type": "freshness",
        "table": "inventory",
        "column": "update_time",
        "max_age_days": 30,
        "severity": "warn",
        "desc": "test freshness",
    }


def test_to_dt_accepts_datetime_and_iso_text():
    value = datetime(2026, 8, 22, 12, 30, 0)
    assert checks._to_dt(value) is value
    assert checks._to_dt("2026-08-22T12:30:00") == value


@pytest.mark.parametrize("value", ["", "   ", "not-a-date", object()])
def test_to_dt_rejects_invalid_timestamps(value):
    with pytest.raises(ValueError):
        checks._to_dt(value)


def test_freshness_check_fails_instead_of_marking_invalid_timestamp_fresh(monkeypatch):
    monkeypatch.setattr(checks, "_sr_scalar", lambda _sql: "not-a-date")
    result = checks.run_check(_freshness_check())
    assert result["status"] == "fail"
    assert "invalid freshness timestamp" in result["message"]

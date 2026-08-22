from datetime import datetime, timedelta

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


def _parity_check():
    return {
        "id": "parity_test",
        "type": "parity",
        "table": "inventory",
        "severity": "error",
        "desc": "test parity",
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


def test_freshness_check_warns_when_source_timestamp_is_in_the_future(monkeypatch):
    future = datetime.now() + timedelta(days=2)
    monkeypatch.setattr(checks, "_sr_scalar", lambda _sql: future)
    result = checks.run_check(_freshness_check())
    assert result["status"] == "warn"
    assert "未来" in result["message"]


@pytest.mark.parametrize("source_count,sink_count", [(None, 12), (12, None), (None, None)])
def test_parity_check_reports_missing_counts_without_arithmetic_errors(monkeypatch, source_count, sink_count):
    monkeypatch.setattr(checks, "_pg_scalar", lambda _sql: source_count)
    monkeypatch.setattr(checks, "_sr_scalar", lambda _sql: sink_count)
    result = checks.run_check(_parity_check())
    assert result["status"] == "fail"
    assert result["actual"] == {"src": source_count, "snk": sink_count}
    assert "未返回有效行数" in result["message"]

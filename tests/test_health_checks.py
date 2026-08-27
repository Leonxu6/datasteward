from datetime import datetime, timedelta, timezone

import pytest

from dm.health import checks


def _freshness_check(max_age_days=30):
    return {"id": "freshness_test", "type": "freshness", "table": "inventory", "column": "update_time", "max_age_days": max_age_days, "severity": "warn", "desc": "test freshness"}


def _volume_check(min_rows=1):
    return {"id": "volume_test", "type": "volume", "min_rows": min_rows, "severity": "error", "desc": "test volume"}


def _parity_check():
    return {"id": "parity_test", "type": "parity", "table": "inventory", "severity": "error", "desc": "test parity"}


def _expectation_check():
    return {"id": "expect_test", "type": "expectation", "table": "inventory", "predicate": "qty < 0", "severity": "error", "desc": "test expectation"}


def test_to_dt_accepts_datetime_and_iso_text():
    value = datetime(2026, 8, 22, 12, 30, 0)
    assert checks._to_dt(value) is value
    assert checks._to_dt("2026-08-22T12:30:00") == value


def test_to_dt_preserves_fractional_seconds_and_timezone_offsets():
    parsed = checks._to_dt("2026-08-22T12:30:00.125+08:00")
    assert parsed.microsecond == 125000
    assert parsed.utcoffset() == timedelta(hours=8)
    assert checks._to_dt("2026-08-22T04:30:00Z").tzinfo == timezone.utc


@pytest.mark.parametrize("value", ["", "   ", "not-a-date", object()])
def test_to_dt_rejects_invalid_timestamps(value):
    with pytest.raises(ValueError):
        checks._to_dt(value)


@pytest.mark.parametrize("value", [None, True, False, -1, 1.5, "12"])
def test_nonnegative_count_rejects_invalid_database_values(value):
    with pytest.raises(ValueError):
        checks._nonnegative_count(value, field="inventory")
    assert checks._nonnegative_count(0, field="inventory") == 0
    assert checks._nonnegative_count(12, field="inventory") == 12


def test_malformed_check_definition_returns_failure_instead_of_raising():
    result = checks.run_check({})
    assert result["status"] == "fail"
    assert result["id"] == "unknown"
    assert result["type"] == "unknown"
    assert result["severity"] == "error"
    assert "检查执行失败" in result["message"]


@pytest.mark.parametrize("min_rows", [None, True, -1, 1.5, "1"])
def test_volume_check_rejects_invalid_minimum_rows_before_queries(monkeypatch, min_rows):
    monkeypatch.setattr(checks, "business_table_names", lambda: (_ for _ in ()).throw(AssertionError("queried tables")))
    result = checks.run_check(_volume_check(min_rows))
    assert result["status"] == "fail"
    assert "min_rows must be a non-negative integer" in result["message"]


def test_expectation_check_fails_cleanly_on_invalid_count(monkeypatch):
    monkeypatch.setattr(checks, "_sr_scalar", lambda _sql: "12")
    result = checks.run_check(_expectation_check())
    assert result["status"] == "fail"
    assert "invalid row count" in result["message"]


@pytest.mark.parametrize("max_age_days", [None, True, -1, 1.5, "30"])
def test_freshness_check_rejects_invalid_age_thresholds_before_queries(monkeypatch, max_age_days):
    monkeypatch.setattr(checks, "_sr_scalar", lambda _sql: (_ for _ in ()).throw(AssertionError("queried warehouse")))
    result = checks.run_check(_freshness_check(max_age_days))
    assert result["status"] == "fail"
    assert "max_age_days must be a non-negative integer" in result["message"]


def test_freshness_check_fails_instead_of_marking_invalid_timestamp_fresh(monkeypatch):
    monkeypatch.setattr(checks, "_sr_scalar", lambda _sql: "not-a-date")
    result = checks.run_check(_freshness_check())
    assert result["status"] == "fail"
    assert "invalid freshness timestamp" in result["message"]


def test_freshness_check_handles_timezone_aware_source_values(monkeypatch):
    recent = datetime.now(timezone.utc) - timedelta(hours=3)
    monkeypatch.setattr(checks, "_sr_scalar", lambda _sql: recent.isoformat())
    result = checks.run_check(_freshness_check())
    assert result["status"] == "ok"


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

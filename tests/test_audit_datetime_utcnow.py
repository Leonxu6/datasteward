from scripts.audit_datetime_utcnow import audit_source


def test_datetime_utcnow_audit_allows_timezone_aware_now():
    assert audit_source("datetime.now(timezone.utc)\n") == []


def test_datetime_utcnow_audit_reports_naive_utcnow():
    assert audit_source("datetime.utcnow()\n") == [
        "datetime.utcnow() style call on line 1"
    ]

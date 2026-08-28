from scripts.audit_naive_datetime_now import audit_source


def test_datetime_now_allows_timezone():
    assert audit_source("datetime.now(timezone.utc)\n") == []


def test_datetime_now_allows_immediate_strftime_for_local_display():
    assert audit_source("datetime.now().strftime('%H:%M:%S')\n") == []


def test_datetime_now_reports_naive_call():
    assert audit_source("datetime.now()\n") == ["datetime.now() without timezone on line 1"]


def test_datetime_now_reports_naive_value_before_formatting():
    source = "stamp = datetime.now()\ntext = stamp.strftime('%H:%M:%S')\n"
    assert audit_source(source) == ["datetime.now() without timezone on line 1"]

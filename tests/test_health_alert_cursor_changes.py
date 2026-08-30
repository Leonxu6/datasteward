from dm.orchestration.health_alerts import failure_cursor


def test_failure_cursor_changes_when_failure_details_change():
    first = failure_cursor(({"id": "inventory", "message": "count=0"},))
    second = failure_cursor(({"id": "inventory", "message": "count=2"},))
    assert first != second


def test_failure_cursor_does_not_store_raw_failure_details():
    cursor = failure_cursor(({"id": "db", "message": "postgres://user:secret@internal"},))
    assert "secret" not in cursor
    assert "internal" not in cursor

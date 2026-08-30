import pytest

from dm.orchestration.health_alerts import (
    HealthAlertInputError,
    failure_cursor,
    normalize_failures,
    render_failure_alert,
)


def test_normalize_failures_filters_sorts_and_sanitizes():
    summary = {
        "results": [
            {"id": "z", "status": "ok", "message": "fine"},
            {"id": 2, "status": "fail", "message": "bad\u202esecret"},
            {"id": "a", "status": "fail", "message": " broken\x00 "},
        ]
    }

    failures = normalize_failures(summary)
    assert failures == (
        {"id": "2", "message": "badsecret"},
        {"id": "a", "message": "broken"},
    )


def test_failure_cursor_is_stable_and_deduplicated():
    failures = ({"id": "b", "message": "x"}, {"id": "a", "message": "y"}, {"id": "a", "message": "y"})
    assert failure_cursor(failures) == failure_cursor(tuple(reversed(failures)))
    assert failure_cursor(failures).count('"a"') == 1


def test_render_failure_alert_caps_expanded_rows():
    failures = tuple({"id": str(index), "message": "bad"} for index in range(10))
    rendered = render_failure_alert(failures)
    assert "另有 2 项失败未展开" in rendered
    assert "[9]" not in rendered


def test_malformed_summary_is_not_treated_as_healthy():
    with pytest.raises(HealthAlertInputError):
        normalize_failures(None)
    with pytest.raises(HealthAlertInputError):
        normalize_failures({"results": "not-a-list"})

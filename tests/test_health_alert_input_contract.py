import pytest

from dm.orchestration.health_alerts import HealthAlertInputError, normalize_failures


@pytest.mark.parametrize(
    "summary",
    [None, {}, {"results": "bad"}, {"results": [None]}, {"results": [{"status": "mystery"}]}],
)
def test_malformed_health_summaries_do_not_look_healthy(summary):
    with pytest.raises(HealthAlertInputError):
        normalize_failures(summary)


def test_supported_non_failure_statuses_remain_healthy():
    assert normalize_failures({"results": [{"status": "ok"}, {"status": "warn"}]}) == ()


def test_non_failure_rows_do_not_require_unique_identifiers():
    summary = {
        "results": [
            {"status": "ok", "id": "shared"},
            {"status": "warn", "id": "shared"},
            {"status": "ok"},
            {"status": "warn"},
        ]
    }
    assert normalize_failures(summary) == ()


def test_duplicate_failure_identifiers_still_fail_closed():
    summary = {
        "results": [
            {"status": "fail", "id": "database", "message": "down"},
            {"status": "fail", "id": "database", "message": "still down"},
        ]
    }
    with pytest.raises(HealthAlertInputError, match="duplicate health result id"):
        normalize_failures(summary)

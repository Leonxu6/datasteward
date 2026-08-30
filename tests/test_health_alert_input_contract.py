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

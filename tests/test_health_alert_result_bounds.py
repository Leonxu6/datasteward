import pytest

from dm.orchestration.health_alerts import HealthAlertInputError, normalize_failures


def test_health_summary_result_count_is_bounded():
    summary = {"results": [{"id": f"c{i}", "status": "ok"} for i in range(1_001)]}
    with pytest.raises(HealthAlertInputError, match="more than 1000"):
        normalize_failures(summary)

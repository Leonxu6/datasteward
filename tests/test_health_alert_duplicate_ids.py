import pytest

from dm.orchestration.health_alerts import HealthAlertInputError, normalize_failures


def test_duplicate_health_check_ids_are_rejected():
    summary = {
        "results": [
            {"id": "inventory", "status": "ok", "message": "fine"},
            {"id": "inventory", "status": "fail", "message": "empty"},
        ]
    }
    with pytest.raises(HealthAlertInputError, match="duplicate health result id"):
        normalize_failures(summary)

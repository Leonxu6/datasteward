import json

from dm.tools.audit_record import safe_json


def test_safe_json_replaces_oversized_payloads_with_bounded_fallback():
    payload = json.loads(safe_json({"value": "x" * 150_000}))
    assert payload["serialization_error"] is True
    assert payload["reason"] == "serialized value exceeds audit limit"
    assert len(payload["repr"]) <= 1000

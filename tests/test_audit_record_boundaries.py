import json

import pytest

from dm.tools.audit_record import elapsed_ms, join_labels, safe_json


def test_safe_json_rejects_nonstandard_numbers_into_fallback():
    payload = json.loads(safe_json({"value": float("nan")}))
    assert payload["serialization_error"] is True
    assert "nan" in payload["repr"].lower()


def test_safe_json_survives_broken_repr_and_recursive_values():
    class Broken:
        def __repr__(self):
            raise RuntimeError("no repr")
        def __str__(self):
            raise RuntimeError("no str")

    payload = json.loads(safe_json(Broken()))
    assert payload == {"serialization_error": True, "repr": "<Broken>"}


def test_join_labels_treats_a_string_as_one_label():
    assert join_labels("PII") == "PII"
    assert join_labels([" PII ", "", "FINANCE"]) == "PII,FINANCE"


def test_join_labels_deduplicates_normalized_values():
    assert join_labels([" PII ", "PII", "FINANCE", "FINANCE"]) == "PII,FINANCE"


def test_join_labels_bounds_aggregate_output():
    labels = [f"{index:03d}-" + "x" * 196 for index in range(60)]
    with pytest.raises(ValueError, match="joined labels"):
        join_labels(labels)


def test_join_labels_rejects_mapping_bytes_and_noniterables():
    for value in ({"PII": True}, b"PII", 7):
        with pytest.raises(ValueError):
            join_labels(value)


def test_elapsed_ms_handles_nonfinite_and_backwards_clocks():
    assert elapsed_ms(1.0, 1.125) == 125
    assert elapsed_ms(2, 1) == 0
    assert elapsed_ms(float("nan"), 2) == 0
    assert elapsed_ms(1, float("inf")) == 0
    assert elapsed_ms("bad", 2) == 0

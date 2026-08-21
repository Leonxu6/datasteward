import json
from datetime import date, datetime
from pathlib import Path

import pytest

from dm.connect.sync_state import (
    atomic_write_json,
    load_json_mapping,
    max_non_null,
    serialize_watermark,
    validate_requested_names,
)


def test_load_json_mapping_handles_missing_corrupt_and_non_object_files(tmp_path):
    path = tmp_path / "state.json"
    assert load_json_mapping(path) == {}
    path.write_text("{bad", encoding="utf-8")
    assert load_json_mapping(path) == {}
    path.write_text("[1, 2]", encoding="utf-8")
    assert load_json_mapping(path) == {}
    path.write_text('{"table": 5}', encoding="utf-8")
    assert load_json_mapping(path) == {"table": 5}


def test_atomic_write_json_replaces_complete_document(tmp_path):
    path = tmp_path / "nested" / "state.json"
    atomic_write_json(path, {"a": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}
    atomic_write_json(path, {"b": "two"})
    assert json.loads(path.read_text(encoding="utf-8")) == {"b": "two"}
    assert not list(path.parent.glob(".state.json.*.tmp"))


def test_atomic_write_json_requires_mapping(tmp_path):
    with pytest.raises(TypeError):
        atomic_write_json(tmp_path / "state.json", [1, 2])


def test_max_non_null_ignores_null_cursor_values():
    assert max_non_null([None, 2, 5, None, 3]) == 5
    assert max_non_null([None, None]) is None


def test_serialize_watermark_preserves_scalars_and_serializes_dates():
    assert serialize_watermark(7) == 7
    assert serialize_watermark("abc") == "abc"
    assert serialize_watermark(date(2026, 8, 21)) == "2026-08-21"
    assert serialize_watermark(datetime(2026, 8, 21, 17, 0)) == "2026-08-21T17:00:00"


def test_requested_names_reject_unknown_and_invalid_names():
    available = ["Inventory", "Vendor"]
    assert validate_requested_names(None, available) is None
    assert validate_requested_names(["Vendor", "Vendor", "Inventory"], available) == ["Vendor", "Inventory"]
    for requested in (["Unknown"], [" Vendor"], [""], [None]):
        with pytest.raises(ValueError):
            validate_requested_names(requested, available)

from datetime import datetime

import pytest

from dm.connect.sync_state import atomic_write_json, load_json_mapping, max_non_null, validate_requested_names


def test_state_paths_must_name_files(tmp_path):
    for path in (None, 7, tmp_path.parent / ".."):
        with pytest.raises(ValueError):
            load_json_mapping(path)
    with pytest.raises(ValueError):
        atomic_write_json(tmp_path, {"cursor": 1})


def test_atomic_state_writer_rejects_nonstandard_json_numbers(tmp_path):
    path = tmp_path / "state.json"
    with pytest.raises(ValueError):
        atomic_write_json(path, {"cursor": float("nan")})
    assert not path.exists()


def test_watermark_max_rejects_scalar_and_mixed_domains():
    for values in (None, "123", {"a": 1}, 7):
        with pytest.raises(ValueError):
            max_non_null(values)
    with pytest.raises(ValueError, match="mutually comparable"):
        max_non_null([1, datetime(2026, 1, 1)])


def test_watermark_max_keeps_none_semantics():
    assert max_non_null([None, None]) is None
    assert max_non_null([None, 3, 1, 2]) == 3


def test_requested_names_reject_scalar_collections_and_bad_available_names():
    for requested in ("orders", {"orders": True}):
        with pytest.raises(ValueError):
            validate_requested_names(requested, ["orders"])
    for available in (None, "orders", [" orders"], ["orders\n"], [7]):
        with pytest.raises(ValueError):
            validate_requested_names(["orders"], available)


def test_requested_names_reject_control_characters():
    with pytest.raises(ValueError, match="control"):
        validate_requested_names(["orders\n"], ["orders"])


def test_available_names_reject_duplicates_instead_of_hiding_registry_errors():
    with pytest.raises(ValueError, match="duplicate available"):
        validate_requested_names(["orders"], ["orders", "orders"])


def test_requested_names_preserve_order_and_deduplicate():
    assert validate_requested_names(
        ["customers", "orders", "customers"],
        (name for name in ["orders", "customers"]),
    ) == ["customers", "orders"]

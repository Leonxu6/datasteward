from types import SimpleNamespace

import pytest

from dm.connect.readiness import build_readiness_report


def _dataset(name="orders", *, columns=None, primary_key=None):
    return SimpleNamespace(
        name=name,
        columns=["id"] if columns is None else columns,
        primary_key=["id"] if primary_key is None else primary_key,
    )


def test_readiness_rejects_scalar_collection_inputs():
    for datasets in (None, "orders", {"orders": _dataset()}):
        with pytest.raises(ValueError):
            build_readiness_report("erp", datasets, [])
    for known in (None, "orders", {"orders": True}):
        with pytest.raises(ValueError):
            build_readiness_report("erp", [_dataset()], known)


def test_readiness_rejects_malformed_known_object_names():
    for known in ([" orders"], [""], ["orders\n"], [7]):
        with pytest.raises(ValueError):
            build_readiness_report("erp", [_dataset()], known)


def test_readiness_rejects_scalar_columns_and_primary_keys():
    with pytest.raises(ValueError, match="columns"):
        build_readiness_report("erp", [_dataset(columns="id")], ["orders"])
    with pytest.raises(ValueError, match="primary_key"):
        build_readiness_report("erp", [_dataset(primary_key="id")], ["orders"])


def test_readiness_rejects_duplicate_or_malformed_columns():
    with pytest.raises(ValueError, match="duplicate"):
        build_readiness_report("erp", [_dataset(columns=["id", "id"])], ["orders"])
    for columns in ([" id"], [""], ["name\n"], [7]):
        with pytest.raises(ValueError, match="column"):
            build_readiness_report("erp", [_dataset(columns=columns, primary_key=[])], ["orders"])


def test_readiness_rejects_duplicate_or_malformed_primary_key_columns():
    with pytest.raises(ValueError, match="duplicate"):
        build_readiness_report("erp", [_dataset(primary_key=["id", "id"])], ["orders"])
    for primary_key in ([" id"], [""], [7]):
        with pytest.raises(ValueError):
            build_readiness_report("erp", [_dataset(primary_key=primary_key)], ["orders"])


def test_readiness_rejects_primary_keys_outside_dataset_columns():
    with pytest.raises(ValueError, match="unknown columns"):
        build_readiness_report(
            "erp",
            [_dataset(columns=["id", "name"], primary_key=["missing_id"])],
            ["orders"],
        )


def test_readiness_keeps_stable_mapping_summary():
    report = build_readiness_report(
        "erp",
        [_dataset("orders"), _dataset("customers", primary_key=[])],
        (name for name in ["orders"]),
    )
    assert report["mapped_object_types"] == ["orders"]
    assert report["unmapped_tables"] == ["customers"]
    assert report["datasets"][0]["pk"] == ["id"]
    assert report["readiness"] == "1/2 表已有对象模型，1 表待建模"

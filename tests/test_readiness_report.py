from types import SimpleNamespace

import pytest

from dm.connect.readiness import build_readiness_report


def dataset(name, columns=("a",), pk=()):
    return SimpleNamespace(name=name, columns=list(columns), primary_key=list(pk))


def test_readiness_report_maps_known_object_types_and_preserves_order():
    report = build_readiness_report(
        "u8_erp",
        [dataset("Inventory", ("id", "name"), ("id",)), dataset("Custom")],
        {"Inventory"},
    )
    assert report["n_tables"] == 2
    assert report["mapped_object_types"] == ["Inventory"]
    assert report["unmapped_tables"] == ["Custom"]
    assert report["datasets"][0] == {
        "name": "Inventory",
        "columns": 2,
        "pk": ["id"],
        "mapped": True,
    }


def test_readiness_report_rejects_duplicate_or_invalid_dataset_names():
    with pytest.raises(ValueError, match="duplicate"):
        build_readiness_report("source", [dataset("orders"), dataset("orders")], set())
    for name in (None, "", " orders", "orders "):
        with pytest.raises(ValueError):
            build_readiness_report("source", [dataset(name)], set())


def test_readiness_report_rejects_missing_dataset_collection_and_columns():
    with pytest.raises(ValueError, match="no dataset"):
        build_readiness_report("source", None, set())
    with pytest.raises(ValueError, match="columns"):
        build_readiness_report("source", [SimpleNamespace(name="orders", primary_key=[])], set())


def test_readiness_report_handles_empty_source_cleanly():
    report = build_readiness_report("empty", [], set())
    assert report["ok"] is True
    assert report["n_tables"] == 0
    assert report["readiness"] == "0/0 表已有对象模型，0 表待建模"

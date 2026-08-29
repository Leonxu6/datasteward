from types import SimpleNamespace

import pytest

from dm.datasets.model import Dataset, Transform
from dm.pipeline import lineage


def _dataset(name, *, source=None, markings=None):
    return Dataset(
        name=name,
        tier="raw" if source else "refined",
        backing=name,
        source=source,
        markings=list(markings or []),
    )


def test_graph_reflects_registry_changes_after_first_read(monkeypatch):
    sources = {"erp": SimpleNamespace(name="erp", markings=["PII"])}
    datasets = {"raw": _dataset("raw", source="erp")}
    transforms = {}
    monkeypatch.setattr(lineage, "SOURCES", sources)
    monkeypatch.setattr(lineage, "DATASETS", datasets)
    monkeypatch.setattr(lineage, "TRANSFORMS", transforms)

    assert [node["id"] for node in lineage.lineage_graph()["nodes"]] == ["dataset:raw", "source:erp"]

    datasets["clean"] = _dataset("clean")
    transforms["refine"] = Transform(
        name="refine",
        kind="refine",
        inputs=["raw"],
        outputs=["clean"],
        column_map={"id": ["id"]},
    )
    graph = lineage.lineage_graph()
    assert "dataset:clean" in [node["id"] for node in graph["nodes"]]
    assert {"from": "transform:refine", "to": "dataset:clean", "kind": "output"} in graph["edges"]


def test_traversal_is_stable_and_shortest_distance_first(monkeypatch):
    monkeypatch.setattr(lineage, "SOURCES", {})
    monkeypatch.setattr(
        lineage,
        "DATASETS",
        {name: _dataset(name) for name in ("a", "b", "c", "d")},
    )
    monkeypatch.setattr(
        lineage,
        "TRANSFORMS",
        {
            "t2": Transform(name="t2", kind="refine", inputs=["a"], outputs=["c"]),
            "t1": Transform(name="t1", kind="refine", inputs=["a"], outputs=["b"]),
            "t3": Transform(name="t3", kind="refine", inputs=["b"], outputs=["d"]),
        },
    )

    first = [node["id"] for node in lineage.impact("a")]
    second = [node["id"] for node in lineage.impact("a")]
    assert first == second
    assert first[:2] == ["transform:t1", "transform:t2"]
    assert first.index("dataset:b") < first.index("transform:t3")


def test_public_queries_reject_unknown_or_malformed_datasets(monkeypatch):
    monkeypatch.setattr(lineage, "DATASETS", {"known": _dataset("known")})
    monkeypatch.setattr(lineage, "SOURCES", {})
    monkeypatch.setattr(lineage, "TRANSFORMS", {})

    for value in ("missing", " known", "known\n", ""):
        with pytest.raises((KeyError, ValueError)):
            lineage.ancestry(value)
        with pytest.raises((KeyError, ValueError)):
            lineage.impact(value)


def test_column_lineage_rejects_ambiguous_producers(monkeypatch):
    monkeypatch.setattr(lineage, "SOURCES", {})
    monkeypatch.setattr(lineage, "DATASETS", {"raw": _dataset("raw"), "out": _dataset("out")})
    monkeypatch.setattr(
        lineage,
        "TRANSFORMS",
        {
            "one": Transform(name="one", kind="refine", inputs=["raw"], outputs=["out"], column_map={"id": ["id"]}),
            "two": Transform(name="two", kind="refine", inputs=["raw"], outputs=["out"], column_map={"id": ["id"]}),
        },
    )

    with pytest.raises(ValueError, match="ambiguous producers"):
        lineage.column_lineage("out", "id")


def test_column_lineage_refuses_multi_input_guessing(monkeypatch):
    monkeypatch.setattr(lineage, "SOURCES", {})
    monkeypatch.setattr(
        lineage,
        "DATASETS",
        {name: _dataset(name) for name in ("left", "right", "joined")},
    )
    monkeypatch.setattr(
        lineage,
        "TRANSFORMS",
        {
            "join": Transform(
                name="join",
                kind="join",
                inputs=["left", "right"],
                outputs=["joined"],
                column_map={"id": ["id"]},
            )
        },
    )

    with pytest.raises(ValueError, match="exactly one input"):
        lineage.column_lineage("joined", "id")


def test_effective_markings_follow_live_upstream_registry(monkeypatch):
    source = SimpleNamespace(name="erp", markings=["PII"])
    datasets = {
        "raw": _dataset("raw", source="erp", markings=["RAW"]),
        "clean": _dataset("clean", markings=["CURATED"]),
    }
    transforms = {
        "refine": Transform(name="refine", kind="refine", inputs=["raw"], outputs=["clean"])
    }
    monkeypatch.setattr(lineage, "SOURCES", {"erp": source})
    monkeypatch.setattr(lineage, "DATASETS", datasets)
    monkeypatch.setattr(lineage, "TRANSFORMS", transforms)

    assert lineage.effective_markings("clean") == ["CURATED", "PII", "RAW"]
    source.markings.append("EXPORT_CONTROLLED")
    assert lineage.effective_markings("clean") == ["CURATED", "EXPORT_CONTROLLED", "PII", "RAW"]

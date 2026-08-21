import json

from dm.datasets.model import _add_dbt


def test_add_dbt_ignores_non_object_manifest(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    (target / "manifest.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("DM_DBT_DIR", str(tmp_path))
    datasets, transforms = {}, {}
    _add_dbt(datasets, transforms)
    assert datasets == {}
    assert transforms == {}


def test_add_dbt_skips_bad_nodes_without_losing_valid_models(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    manifest = {
        "nodes": {
            "model.project.bad": "broken",
            "model.project.blank": {"resource_type": "model", "name": ""},
            "model.project.good": {"resource_type": "model", "name": "good"},
        },
        "parent_map": {"model.project.good": "not-a-list"},
    }
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("DM_DBT_DIR", str(tmp_path))
    datasets, transforms = {}, {}
    _add_dbt(datasets, transforms)
    assert list(datasets) == ["good"]
    assert transforms["dbt__good"].inputs == []

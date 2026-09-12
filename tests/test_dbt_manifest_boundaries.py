import pytest

from dm.datasets import dbt_manifest


def test_load_manifest_rejects_non_paths_and_oversized_files(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        dbt_manifest.load_manifest(None)
    path = tmp_path / "manifest.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(dbt_manifest, "_MAX_MANIFEST_BYTES", 1)
    assert dbt_manifest.load_manifest(path) is None


def test_load_manifest_rejects_directories(tmp_path):
    assert dbt_manifest.load_manifest(tmp_path) is None


def test_iter_nodes_validates_manifest_and_resource_type():
    with pytest.raises(ValueError):
        list(dbt_manifest.iter_nodes(None, resource_type="model"))
    for resource_type in ("", " model", "model\n", "mod\u200del", "mod\ud800el", 7):
        with pytest.raises(ValueError):
            list(dbt_manifest.iter_nodes({}, resource_type=resource_type))


def test_iter_nodes_skips_malformed_unique_ids_and_names():
    manifest = {
        "nodes": {
            "model.good": {"resource_type": "model", "name": "good"},
            " model.bad": {"resource_type": "model", "name": "bad"},
            "model.control\n": {"resource_type": "model", "name": "bad"},
            "model.hidden\u200d": {"resource_type": "model", "name": "hidden"},
            "model.surrogate\ud800": {"resource_type": "model", "name": "surrogate"},
            "model.empty": {"resource_type": "model", "name": ""},
            "model.bad-name": {"resource_type": "model", "name": "bad\n"},
            "model.hidden-name": {"resource_type": "model", "name": "ba\u200dd"},
            7: {"resource_type": "model", "name": "numeric-id"},
        }
    }
    assert list(dbt_manifest.iter_nodes(manifest, resource_type="model")) == [
        ("model.good", {"resource_type": "model", "name": "good"})
    ]


def test_parent_names_validates_lookup_key_and_skips_malformed_parents():
    manifest = {
        "parent_map": {
            "model.child": [
                "model.a",
                " model.b",
                "model.bad\n",
                "model.hidden\u200d",
                "model.surrogate\ud800",
                "model.a",
                7,
                "seed.c",
            ]
        }
    }
    assert dbt_manifest.parent_names(manifest, "model.child") == ["a", "c"]
    for unique_id in ("", " model.child", "model.child\n", "model.child\u200d", "model.child\ud800", 7):
        with pytest.raises(ValueError):
            dbt_manifest.parent_names(manifest, unique_id)


def test_model_layer_requires_mapping_and_falls_back_for_dirty_fqn():
    with pytest.raises(ValueError):
        dbt_manifest.model_layer(None)
    assert dbt_manifest.model_layer({"fqn": ["project", "dws", "orders"]}) == "dws"
    assert dbt_manifest.model_layer({"fqn": ["project", " dws", "orders"]}) == "dw"
    assert dbt_manifest.model_layer({"fqn": ["project", "dws\n", "orders"]}) == "dw"
    assert dbt_manifest.model_layer({"fqn": ["project", "dw\u200ds", "orders"]}) == "dw"
    assert dbt_manifest.model_layer({"fqn": ["project", "dw\ud800s", "orders"]}) == "dw"

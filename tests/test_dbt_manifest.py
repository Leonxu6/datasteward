import json

from dm.datasets.dbt_manifest import iter_nodes, load_manifest, model_layer, parent_names


def test_load_manifest_rejects_missing_corrupt_and_non_object_documents(tmp_path):
    path = tmp_path / "manifest.json"
    assert load_manifest(path) is None
    path.write_text("{bad", encoding="utf-8")
    assert load_manifest(path) is None
    path.write_text("[]", encoding="utf-8")
    assert load_manifest(path) is None
    path.write_text('{"nodes": {}}', encoding="utf-8")
    assert load_manifest(path) == {"nodes": {}}


def test_iter_nodes_skips_wrong_types_and_malformed_entries():
    manifest = {
        "nodes": {
            "model.project.good": {"resource_type": "model", "name": "good"},
            "seed.project.seed": {"resource_type": "seed", "name": "seed"},
            "model.project.blank": {"resource_type": "model", "name": ""},
            "model.project.bad": "not-a-node",
        }
    }
    assert list(iter_nodes(manifest, resource_type="model")) == [
        ("model.project.good", {"resource_type": "model", "name": "good"})
    ]
    assert list(iter_nodes({"nodes": []}, resource_type="model")) == []


def test_parent_names_deduplicate_and_ignore_malformed_dependencies():
    manifest = {
        "parent_map": {
            "model.project.orders": [
                "source.project.erp.orders_raw",
                "model.project.customers",
                "model.project.customers",
                None,
            ]
        }
    }
    assert parent_names(manifest, "model.project.orders") == ["orders_raw", "customers"]
    assert parent_names({"parent_map": []}, "model.project.orders") == []


def test_model_layer_handles_expected_and_malformed_fqn_shapes():
    assert model_layer({"fqn": ["project", "dwd", "orders"]}) == "dwd"
    assert model_layer({"fqn": ["project"]}) == "dw"
    assert model_layer({"fqn": "project.dwd.orders"}) == "dw"
    assert model_layer({}) == "dw"

import json

from dm.datasets.model import Dataset, Tier, _add_dbt


def test_add_dbt_registers_seed_models_and_known_parents(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    manifest = {
        "nodes": {
            "seed.project.country_codes": {
                "resource_type": "seed",
                "name": "country_codes",
                "description": "Reference countries",
            },
            "model.project.orders_dwd": {
                "resource_type": "model",
                "name": "orders_dwd",
                "description": "Clean orders",
                "fqn": ["project", "dwd", "orders_dwd"],
            },
        },
        "parent_map": {
            "model.project.orders_dwd": ["source.project.erp.raw_orders", "seed.project.country_codes"]
        },
    }
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("DM_DBT_DIR", str(tmp_path))

    datasets = {"raw_orders": Dataset("raw_orders", Tier.RAW.value, "raw_orders")}
    transforms = {}
    _add_dbt(datasets, transforms)

    assert datasets["country_codes"].tier == Tier.DW.value
    assert datasets["orders_dwd"].transform == "dbt__orders_dwd"
    assert transforms["dbt__orders_dwd"].inputs == ["raw_orders", "country_codes"]
    assert transforms["dbt__orders_dwd"].outputs == ["orders_dwd"]

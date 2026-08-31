from unittest.mock import patch

import dm.pipeline.health as health


def test_cdc_reconcile_rejects_unsafe_or_duplicate_table_names_before_connecting():
    registries = (
        "inventory",
        ["inventory", "inventory"],
        ["inventory; DROP TABLE audit_log"],
        ["quoted-table"],
        [""],
        ["a" * 129],
        [f"table_{index}" for index in range(101)],
    )
    for registry in registries:
        with (
            patch.object(health, "business_table_names", return_value=registry),
            patch.object(health, "_pg") as pg,
            patch.object(health, "connect_ro") as warehouse,
        ):
            assert health.cdc_reconcile() == {"error": "source/sink reconciliation failed"}
            pg.assert_not_called()
            warehouse.assert_not_called()


def test_business_table_registry_accepts_unique_safe_identifiers():
    assert health._business_tables(["inventory", "sales_order_2026"]) == [
        "inventory",
        "sales_order_2026",
    ]

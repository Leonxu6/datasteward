import pytest

from dm.security import policy
from dm.security.model import User


def test_lineage_marking_failures_do_not_fail_open(monkeypatch):
    import dm.pipeline.lineage as lineage

    def broken_markings(_table):
        raise RuntimeError("lineage unavailable")

    monkeypatch.setattr(lineage, "effective_markings", broken_markings)
    with pytest.raises(RuntimeError, match="lineage unavailable"):
        policy.can_read_table(User("alice"), "inventory")


def test_row_policy_requires_its_subject_attribute():
    with pytest.raises(PermissionError, match="warehouse_id"):
        policy.row_filter(User("alice", role="仓管", attrs={}), "inventory")


def test_row_policy_preserves_falsey_but_present_values():
    assert policy.row_filter(User("alice", role="仓管", attrs={"warehouse_id": 0}), "inventory") == (
        "warehouse_id",
        0,
    )


def test_query_boundary_rejects_malformed_tables_and_sql():
    user = User("alice")
    with pytest.raises(ValueError, match="tables_touched"):
        policy.enforce_query(user, "select 1", "inventory")
    with pytest.raises(ValueError, match="control"):
        policy.enforce_query(user, "select\x00 1", [])
    with pytest.raises(ValueError, match="table"):
        policy.enforce_query(user, "select 1", [" inventory"])


def test_mask_rejects_malformed_row_widths_before_indexing():
    with pytest.raises(ValueError, match="row width"):
        policy.apply_mask(["id", "phone"], [(1,)], ["phone"])


def test_public_policy_helpers_validate_subject_and_names():
    with pytest.raises(ValueError, match="User"):
        policy.can_read_table(object(), "inventory")
    with pytest.raises(ValueError, match="action"):
        policy.can_execute_action(User("alice"), "create_delivery\n")
    with pytest.raises(ValueError, match="table"):
        policy.row_filter(User("alice"), " inventory")

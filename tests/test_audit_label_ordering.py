import pytest

from dm.tools.audit_record import join_labels


def test_audit_labels_reject_unordered_collections():
    for values in ({"beta", "alpha"}, frozenset({"beta", "alpha"})):
        with pytest.raises(ValueError, match="ordered iterable"):
            join_labels(values)


def test_audit_labels_preserve_explicit_sequence_order():
    assert join_labels(["beta", "alpha"]) == "beta,alpha"

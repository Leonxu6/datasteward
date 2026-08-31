from dm.tools.audit_record import join_labels


def test_audit_labels_are_single_line_and_direction_safe():
    assert join_labels(["PII\nrestricted", "finance\u202ehidden"]) == "PII restricted,finance hidden"

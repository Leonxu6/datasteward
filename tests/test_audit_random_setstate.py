from scripts.audit_random_setstate import audit_source


def test_random_state_audit_allows_local_generators():
    assert audit_source("rng = random.Random(7)\n") == []


def test_random_state_audit_reports_global_state_replacement():
    assert audit_source("random.setstate(state)\n") == ["random.setstate() replaces module-global RNG state on line 1"]

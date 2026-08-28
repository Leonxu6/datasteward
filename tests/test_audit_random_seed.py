from scripts.audit_random_seed import audit_source


def test_random_seed_audit_allows_local_rng():
    assert audit_source("rng = random.Random(7)\n") == []


def test_random_seed_audit_reports_global_state_mutation():
    assert audit_source("random.seed(7)\n") == [
        "random.seed() mutates module-global RNG state on line 1"
    ]

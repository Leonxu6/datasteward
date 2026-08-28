from scripts.audit_builtin_hash import audit_source


def test_builtin_hash_allows_stable_digest():
    assert audit_source("hashlib.sha256(data).hexdigest()\n") == []


def test_builtin_hash_reports_process_randomized_hash():
    assert audit_source("key = hash(value)\n") == [
        "builtin hash() on line 1; use a stable digest for persisted identities"
    ]

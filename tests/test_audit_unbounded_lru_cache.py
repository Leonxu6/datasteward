from scripts.audit_unbounded_lru_cache import audit_source


def test_lru_audit_allows_bounded_cache():
    assert audit_source("functools.lru_cache(maxsize=256)()\n") == []


def test_lru_audit_reports_none_maxsize():
    assert audit_source("functools.lru_cache(maxsize=None)()\n") == ["unbounded functools.lru_cache() on line 1"]

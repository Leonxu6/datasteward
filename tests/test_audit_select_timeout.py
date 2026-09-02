from scripts.audit_select_timeout import audit_source

def test_select_allows_finite_timeout():
    assert audit_source("select.select(r, w, x, 1.0)\n") == []

def test_select_reports_unbounded_wait():
    assert audit_source("select.select(r, w, x)\n") == ["select.select without finite timeout on line 1"]

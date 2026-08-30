from scripts.audit_numpy_global_state import audit_source


def test_numpy_state_audit_allows_local_operations():
    assert audit_source("np.asarray(values)\n") == []


def test_numpy_state_audit_reports_global_mutation():
    assert audit_source("np.seterr(all='raise')\n") == ["NumPy global state mutation via seterr() on line 1"]

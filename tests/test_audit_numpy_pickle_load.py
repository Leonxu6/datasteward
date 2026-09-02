from scripts.audit_numpy_pickle_load import audit_source

def test_numpy_load_allows_pickle_disabled():
    assert audit_source("np.load(path, allow_pickle=False)\n") == []

def test_numpy_load_reports_pickle_enabled():
    assert audit_source("np.load(path, allow_pickle=True)\n") == ["np.load enables pickle deserialization on line 1"]
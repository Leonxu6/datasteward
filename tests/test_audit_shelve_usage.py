from scripts.audit_shelve_usage import audit_source


def test_shelve_audit_allows_json_storage():
    assert audit_source("json.dump(data, handle)\n") == []


def test_shelve_audit_reports_pickle_backed_storage():
    assert audit_source("shelve.open(path)\n") == ["shelve.open() uses pickle-backed persistence on line 1"]

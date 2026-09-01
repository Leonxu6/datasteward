from scripts.audit_urllib_install_opener import audit_source


def test_opener_audit_allows_local_openers():
    assert audit_source("opener = urllib.request.build_opener()\n") == []


def test_opener_audit_reports_global_opener_installation():
    assert audit_source("urllib.request.install_opener(opener)\n") == ["urllib.request.install_opener() mutates global URL handling on line 1"]

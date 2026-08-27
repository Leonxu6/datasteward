from scripts.audit_unverified_ssl_context import audit_source


def test_unverified_ssl_audit_allows_default_contexts():
    assert audit_source("import ssl\ncontext = ssl.create_default_context()\n") == []


def test_unverified_ssl_audit_reports_disabled_verification():
    assert audit_source("import ssl\ncontext = ssl._create_unverified_context()\n") == [
        "ssl._create_unverified_context() call on line 2"
    ]

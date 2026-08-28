from scripts.audit_open_text_encoding import audit_source


def test_open_encoding_allows_binary_and_explicit_text_encoding():
    assert audit_source("open('x','rb')\nopen('x', encoding='utf-8')\n") == []


def test_open_encoding_reports_default_text_encoding():
    assert audit_source("open('x','w')\n") == ["text open() without explicit encoding on line 1"]

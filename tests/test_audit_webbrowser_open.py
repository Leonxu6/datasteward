from scripts.audit_webbrowser_open import audit_source

def test_webbrowser_audit_ignores_lookup():
    assert audit_source("webbrowser.get()\n") == []

def test_webbrowser_audit_reports_launch():
    assert audit_source("webbrowser.open(url)\n") == ["webbrowser.open launches a browser side effect on line 1"]

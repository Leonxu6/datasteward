from scripts.audit_interactive_input import audit_source


def test_interactive_input_audit_allows_nonblocking_configuration():
    assert audit_source("value = config.get('name')\n") == []


def test_interactive_input_audit_reports_blocking_prompt():
    assert audit_source("name = input('name: ')\n") == [
        "interactive input() call on line 1"
    ]

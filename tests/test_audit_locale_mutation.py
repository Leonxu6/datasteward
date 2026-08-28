from scripts.audit_locale_mutation import audit_source


def test_locale_audit_allows_local_formatters():
    assert audit_source("formatter = BabelFormatter()\n") == []


def test_locale_audit_reports_process_mutation():
    assert audit_source("locale.setlocale(locale.LC_ALL, 'C')\n") == [
        "locale.setlocale() mutates process-wide locale on line 1"
    ]

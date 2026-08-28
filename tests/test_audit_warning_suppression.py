from scripts.audit_warning_suppression import audit_source


def test_warning_audit_allows_default_filtering():
    assert audit_source("warnings.simplefilter('default')\n") == []


def test_warning_audit_reports_global_ignore():
    assert audit_source("warnings.filterwarnings('ignore')\n") == [
        "global warning suppression on line 1; scope or document the ignored category"
    ]

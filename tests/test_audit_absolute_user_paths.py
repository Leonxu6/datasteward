from scripts.audit_absolute_user_paths import audit_source


def test_absolute_user_path_audit_allows_relative_and_home_expansion_paths():
    assert audit_source("paths = ['data/file.txt', '~/state.db']\n") == []


def test_absolute_user_path_audit_reports_user_home_literals():
    failures = audit_source("a = '/Users/alice/file.txt'\nb = '/home/bob/data'\n")
    assert failures == [
        "machine-specific user path on line 1",
        "machine-specific user path on line 2",
    ]

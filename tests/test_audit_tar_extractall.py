from scripts.audit_tar_extractall import audit_source


def test_archive_extract_allows_member_inspection_only():
    assert audit_source("members = archive.getmembers()\n") == []


def test_archive_extract_reports_direct_extraction():
    assert audit_source("archive.extractall(dest)\n") == [
        "archive extractall() on line 1; validate member paths before extraction"
    ]

from scripts.audit_zip_extractall import audit_source


def test_zip_audit_allows_member_inspection():
    assert audit_source("archive.infolist()\n") == []


def test_zip_audit_reports_extractall():
    assert audit_source("archive.extractall(target)\n") == ["ZipFile.extractall() needs traversal review on line 1"]

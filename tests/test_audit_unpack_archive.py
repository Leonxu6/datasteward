from scripts.audit_unpack_archive import audit_source


def test_unpack_archive_allows_explicit_member_handling():
    assert audit_source("safe_extract(path, dest)\n") == []


def test_unpack_archive_reports_generic_unpacking():
    assert audit_source("shutil.unpack_archive(path, dest)\n") == [
        "shutil.unpack_archive() on line 1; verify extraction stays inside the destination"
    ]

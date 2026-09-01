from scripts.audit_tempfile_tempdir import audit_source


def test_tempdir_audit_allows_explicit_directory_arguments():
    assert audit_source("tempfile.NamedTemporaryFile(dir=path)\n") == []


def test_tempdir_audit_reports_process_default_replacement():
    assert audit_source("tempfile.tempdir = '/tmp/app'\n") == ["tempfile.tempdir replacement mutates process temporary-file policy on line 1"]

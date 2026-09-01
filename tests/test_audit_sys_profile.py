from scripts.audit_sys_profile import audit_source


def test_sys_profile_audit_allows_getprofile():
    assert audit_source("sys.getprofile()\n") == []


def test_sys_profile_audit_reports_profile_installation():
    assert audit_source("sys.setprofile(profile)\n") == ["sys.setprofile() installs a runtime profiling hook on line 1"]

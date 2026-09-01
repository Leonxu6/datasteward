from scripts.audit_numpy_printoptions import audit_source


def test_numpy_printoptions_audit_allows_local_formatting():
    assert audit_source("text = array2string(values)\n") == []


def test_numpy_printoptions_audit_reports_global_rendering_changes():
    assert audit_source("np.set_printoptions(precision=3)\n") == ["numpy.set_printoptions() mutates global array rendering on line 1"]

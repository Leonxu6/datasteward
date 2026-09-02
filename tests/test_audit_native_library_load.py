from scripts.audit_native_library_load import audit_source

def test_native_library_audit_ignores_structure_helpers():
    assert audit_source("ctypes.sizeof(MyStruct)\n") == []

def test_native_library_audit_reports_dynamic_load():
    assert audit_source("ctypes.CDLL(path)\n") == ["ctypes.CDLL loads native code at runtime on line 1"]
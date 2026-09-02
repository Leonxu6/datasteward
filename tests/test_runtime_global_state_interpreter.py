from scripts import audit_runtime_global_state as audit


def test_interpreter_scheduling_and_loader_mutations_are_reported():
    source = """
import sys
sys.setswitchinterval(0.01)
sys.setdlopenflags(2)
"""
    findings = audit.findings_for_source(source, path="runtime.py")
    assert len(findings) == 2
    assert any("sys.setswitchinterval" in item for item in findings)
    assert any("sys.setdlopenflags" in item for item in findings)

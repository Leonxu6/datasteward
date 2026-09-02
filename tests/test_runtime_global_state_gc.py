from scripts import audit_runtime_global_state as audit


def test_garbage_collector_freeze_mutations_are_reported():
    source = """
import gc
gc.freeze()
gc.unfreeze()
"""
    findings = audit.findings_for_source(source, path="memory.py")
    assert len(findings) == 2
    assert any("gc.freeze" in item for item in findings)
    assert any("gc.unfreeze" in item for item in findings)

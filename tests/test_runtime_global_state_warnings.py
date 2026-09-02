from scripts import audit_runtime_global_state as audit


def test_warning_filter_mutations_are_reported():
    source = """
import warnings
warnings.filterwarnings('error')
warnings.simplefilter('default')
"""
    findings = audit.findings_for_source(source, path="warnings_config.py")
    assert len(findings) == 2
    assert any("warnings.filterwarnings" in item for item in findings)
    assert any("warnings.simplefilter" in item for item in findings)

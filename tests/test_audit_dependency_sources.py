from scripts.audit_dependency_sources import audit_dependencies

def test_dependency_sources_accept_index_constraints():assert audit_dependencies(['requests>=2.31','pandas>=2'])==[]
def test_dependency_sources_report_direct_url():assert audit_dependencies(['demo @ https://example.com/demo.whl'])==['direct dependency source is not allowed: demo @ https://example.com/demo.whl']

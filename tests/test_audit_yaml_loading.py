from scripts.audit_yaml_loading import audit_source

def test_yaml_loading_audit_accepts_safe_load():assert audit_source('yaml.safe_load(text)\n')==[]
def test_yaml_loading_audit_reports_load():assert audit_source('yaml.load(text)\n')==['unsafe yaml.load() on line 1; use safe_load']

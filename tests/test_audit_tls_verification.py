from scripts.audit_tls_verification import audit_source

def test_tls_audit_accepts_default_verification():assert audit_source('requests.get(url,timeout=5)\n')==[]
def test_tls_audit_reports_verify_false():assert audit_source('requests.get(url,verify=False)\n')==['TLS verification disabled with verify=False on line 1']

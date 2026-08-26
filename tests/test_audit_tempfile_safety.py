from scripts.audit_tempfile_safety import audit_source

def test_tempfile_audit_accepts_named_file():assert audit_source('tempfile.NamedTemporaryFile()\n')==[]
def test_tempfile_audit_reports_mktemp():assert audit_source('tempfile.mktemp()\n')==['insecure tempfile.mktemp() on line 1']

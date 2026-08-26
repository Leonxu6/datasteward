from scripts.audit_weak_hash import audit_source

def test_weak_hash_audit_accepts_sha256():assert audit_source('hashlib.sha256(data)\n')==[]
def test_weak_hash_audit_reports_md5_sha1():assert audit_source('hashlib.md5(data)\nhashlib.sha1(data)\n')==['weak hash hashlib.md5() on line 1','weak hash hashlib.sha1() on line 2']

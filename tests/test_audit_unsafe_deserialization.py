from scripts.audit_unsafe_deserialization import audit_source

def test_deserialization_audit_accepts_json():assert audit_source('import json\n')==[]
def test_deserialization_audit_reports_pickle_marshal():
    failures=audit_source('import pickle\nfrom marshal import loads\n');assert len(failures)==2;assert 'pickle' in failures[0];assert 'marshal' in failures[1]

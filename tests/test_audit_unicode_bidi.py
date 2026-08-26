from scripts.audit_unicode_bidi import audit_text

def test_bidi_audit_accepts_regular_unicode():assert audit_text("hello 世界") == []
def test_bidi_audit_reports_override():assert audit_text("safe\u202etxt")==["bidirectional control character on line 1"]

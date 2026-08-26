from scripts.audit_merge_markers import audit_text

def test_merge_marker_audit_accepts_clean_text():assert audit_text('clean\ntext\n')==[]
def test_merge_marker_audit_reports_conflict_boundaries():
    text='<'*7+' HEAD\nours\n'+'>'*7+' branch\n';assert audit_text(text)==['unresolved merge marker on line 1','unresolved merge marker on line 3']

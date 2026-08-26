from pathlib import Path
from scripts.audit_unicode_paths import audit_paths

def test_unicode_path_audit_accepts_distinct_paths():assert audit_paths([Path('docs/a.md'),Path('docs/b.md')])==[]
def test_unicode_path_audit_reports_nfc_collision():
    composed=Path('docs/café.md');decomposed=Path('docs/cafe\u0301.md');assert len(audit_paths([composed,decomposed]))==1

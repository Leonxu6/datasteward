import json
from pathlib import Path
from scripts.audit_json_syntax import audit_file

def test_json_syntax_accepts_valid_json(tmp_path: Path):
    path=tmp_path/"ok.json"; path.write_text(json.dumps({"ok":True}),encoding="utf-8"); assert audit_file(path)==[]

def test_json_syntax_reports_invalid_json(tmp_path: Path):
    path=tmp_path/"bad.json"; path.write_text('{"ok":',encoding="utf-8"); assert "invalid JSON" in audit_file(path)[0]

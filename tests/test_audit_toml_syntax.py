from pathlib import Path
from scripts.audit_toml_syntax import audit_file

def test_toml_syntax_accepts_valid_toml(tmp_path:Path):
    p=tmp_path/"ok.toml";p.write_text('[project]\nname="demo"\n',encoding="utf-8");assert audit_file(p)==[]

def test_toml_syntax_reports_invalid_toml(tmp_path:Path):
    p=tmp_path/"bad.toml";p.write_text('[project\n',encoding="utf-8");assert "invalid TOML" in audit_file(p)[0]

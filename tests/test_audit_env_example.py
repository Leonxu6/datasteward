from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_env_example.py"
spec = spec_from_file_location("audit_env_example", MODULE_PATH)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_audit_accepts_comments_blank_lines_and_clean_settings(tmp_path):
    path = tmp_path / ".env.example"
    path.write_text("# comment\n\nFOO=bar\nEMPTY=\n", encoding="utf-8")
    assert module.audit_env_file(path) == []


def test_audit_reports_invalid_duplicate_and_padded_settings(tmp_path):
    path = tmp_path / ".env.example"
    path.write_text("bad-key=x\nFOO=one\nFOO=two\nBAR= padded \nMISSING\n", encoding="utf-8")
    messages = [message for _, message in module.audit_env_file(path)]
    assert "invalid environment variable name" in messages
    assert "duplicate setting: FOO" in messages
    assert "BAR value has surrounding whitespace" in messages
    assert "setting must contain '='" in messages

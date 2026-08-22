from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_ci_contract.py"
spec = spec_from_file_location("audit_ci_contract", MODULE_PATH)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_contract_accepts_all_required_ci_stages(tmp_path):
    path = tmp_path / "ci.yml"
    path.write_text("\n".join(module._REQUIRED.values()), encoding="utf-8")
    assert module.missing_ci_contract(path) == ()


def test_contract_reports_missing_compose_validation(tmp_path):
    path = tmp_path / "ci.yml"
    text = "\n".join(value for name, value in module._REQUIRED.items() if name != "compose validation")
    path.write_text(text, encoding="utf-8")
    assert module.missing_ci_contract(path) == ("compose validation",)

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_dbt_artifacts.py"
spec = spec_from_file_location("audit_dbt_artifacts", MODULE_PATH)
module = module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def test_manifest_and_run_results_shapes_are_accepted(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"nodes": {}, "sources": {}}), encoding="utf-8")
    results = tmp_path / "run_results.json"
    results.write_text(json.dumps({"results": []}), encoding="utf-8")
    assert module.validate_artifact(manifest) == []
    assert module.validate_artifact(results) == []


def test_artifact_audit_reports_missing_invalid_and_wrong_shapes(tmp_path):
    assert module.validate_artifact(tmp_path / "manifest.json") == ["missing artifact: manifest.json"]
    manifest = tmp_path / "manifest.json"
    manifest.write_text("[]", encoding="utf-8")
    assert module.validate_artifact(manifest) == ["manifest.json must contain a JSON object"]
    results = tmp_path / "run_results.json"
    results.write_text(json.dumps({"results": {}}), encoding="utf-8")
    assert module.validate_artifact(results) == ["run_results.json 'results' must be an array"]

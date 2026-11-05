import json

import dm.health.checks as checks


_CHK = {"id": "dbt_tests", "type": "dbt", "severity": "error", "desc": "dbt tests"}


def _write_results(tmp_path, text: str):
    target = tmp_path / "target"
    target.mkdir()
    (target / "run_results.json").write_text(text, encoding="utf-8")


def test_dbt_health_accepts_well_formed_test_results(tmp_path, monkeypatch):
    _write_results(
        tmp_path,
        json.dumps({"results": [{"unique_id": "test.project.not_null_orders", "status": "pass"}]}),
    )
    monkeypatch.setenv("DM_DBT_DIR", str(tmp_path))
    result = checks._dbt_tests_result(_CHK)
    assert result["status"] == "ok"
    assert result["actual"] == 1


def test_dbt_health_rejects_ambiguous_json(tmp_path, monkeypatch):
    monkeypatch.setenv("DM_DBT_DIR", str(tmp_path))
    for text in (
        '{"results": [], "elapsed": NaN}',
        '{"results": [], "results": [{"unique_id":"test.shadow","status":"fail"}]}',
    ):
        if (tmp_path / "target").exists():
            (tmp_path / "target" / "run_results.json").unlink(missing_ok=True)
            (tmp_path / "target").rmdir()
        _write_results(tmp_path, text)
        result = checks._dbt_tests_result(_CHK)
        assert result["status"] == "fail"
        assert result["actual"] is None
        assert "标准 JSON" in result["message"]


def test_dbt_health_rejects_malformed_result_items(tmp_path, monkeypatch):
    _write_results(tmp_path, json.dumps({"results": ["not-an-object"]}))
    monkeypatch.setenv("DM_DBT_DIR", str(tmp_path))
    result = checks._dbt_tests_result(_CHK)
    assert result["status"] == "fail"
    assert "标准 JSON" in result["message"]


def test_dbt_health_rejects_missing_result_identity(tmp_path, monkeypatch):
    _write_results(tmp_path, json.dumps({"results": [{"status": "pass"}]}))
    monkeypatch.setenv("DM_DBT_DIR", str(tmp_path))
    result = checks._dbt_tests_result(_CHK)
    assert result["status"] == "fail"
    assert "结构异常" in result["message"]


def test_dbt_health_uses_descriptor_owned_artifact_reads(tmp_path, monkeypatch):
    _write_results(tmp_path, '{"results": []}')
    path = tmp_path / "target" / "run_results.json"

    def reject_path_read(*_args, **_kwargs):
        raise AssertionError("path-based reads reintroduce a size-check race")

    monkeypatch.setattr(checks.Path, "read_text", reject_path_read)
    assert checks._load_dbt_results(path) == []

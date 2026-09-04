import dm.health.checks as checks


def test_run_check_redacts_backend_exception_details(monkeypatch):
    monkeypatch.setattr(
        checks,
        "business_table_names",
        lambda: (_ for _ in ()).throw(RuntimeError("postgres://user:secret@host/db")),
    )

    result = checks.run_check({
        "id": "volume",
        "type": "volume",
        "min_rows": 1,
        "severity": "error",
        "desc": "volume",
    })

    assert result["status"] == "fail"
    assert result["message"] == "检查执行失败（RuntimeError）"
    assert "secret" not in result["message"]
    assert "host" not in result["message"]

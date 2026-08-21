from types import SimpleNamespace

from dm.connect import onboard as onboard_module


def test_list_command_returns_success(monkeypatch, capsys):
    monkeypatch.setattr(onboard_module.sys, "argv", ["dm-connect", "list"])
    monkeypatch.setattr(
        onboard_module,
        "list_sources",
        lambda: [SimpleNamespace(name="files", source_type="file", description="local files")],
    )
    assert onboard_module.main() == 0
    assert "files" in capsys.readouterr().out


def test_test_command_returns_failure_for_connector_exception(monkeypatch, capsys):
    monkeypatch.setattr(onboard_module.sys, "argv", ["dm-connect", "test", "missing"])
    monkeypatch.setattr(onboard_module, "get_connector", lambda name: (_ for _ in ()).throw(KeyError(name)))
    assert onboard_module.main() == 1
    assert "❌" in capsys.readouterr().out


def test_onboard_command_propagates_structured_failure(monkeypatch, capsys):
    monkeypatch.setattr(onboard_module.sys, "argv", ["dm-connect", "onboard", "source"])
    monkeypatch.setattr(
        onboard_module,
        "onboard",
        lambda name: {"source": name, "ok": False, "stage": "connect", "error": "offline"},
    )
    assert onboard_module.main() == 1
    assert "connect" in capsys.readouterr().out


def test_invalid_usage_returns_cli_error_code(monkeypatch, capsys):
    monkeypatch.setattr(onboard_module.sys, "argv", ["dm-connect", "unknown"])
    assert onboard_module.main() == 2
    assert "CLI" in capsys.readouterr().out

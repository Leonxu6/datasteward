from types import SimpleNamespace

from dm.connect import onboard as onboard_module


class Connector:
    def __init__(self, *, test_result=(True, "ok"), test_error=None, datasets=None, introspect_error=None):
        self.test_result = test_result
        self.test_error = test_error
        self.datasets = [] if datasets is None else datasets
        self.introspect_error = introspect_error

    def test_connection(self):
        if self.test_error:
            raise self.test_error
        return self.test_result

    def introspect(self):
        if self.introspect_error:
            raise self.introspect_error
        return self.datasets


def test_onboard_reports_connector_resolution_failure(monkeypatch):
    monkeypatch.setattr(
        onboard_module,
        "get_connector",
        lambda name: (_ for _ in ()).throw(KeyError(f"missing {name} password=secret")),
    )
    report = onboard_module.onboard("missing")
    assert report["ok"] is False
    assert report["stage"] == "resolve"
    assert report["error"] == "resolve failed (KeyError)"
    assert "secret" not in report["error"]


def test_onboard_reports_connection_exception_and_negative_probe(monkeypatch):
    monkeypatch.setattr(
        onboard_module,
        "get_connector",
        lambda name: Connector(test_error=RuntimeError("postgres://user:secret@host/db")),
    )
    report = onboard_module.onboard("source")
    assert report["stage"] == "connect"
    assert report["error"] == "connect failed (RuntimeError)"
    assert "secret" not in report["error"]

    monkeypatch.setattr(
        onboard_module,
        "get_connector",
        lambda name: Connector(test_result=(False, "denied password=secret")),
    )
    report = onboard_module.onboard("source")
    assert report["stage"] == "connect"
    assert report["error"] == "connect failed"
    assert "secret" not in report["error"]


def test_onboard_reports_introspection_and_report_shape_failures(monkeypatch):
    monkeypatch.setattr(
        onboard_module,
        "get_connector",
        lambda name: Connector(introspect_error=RuntimeError("schema timeout password=secret")),
    )
    report = onboard_module.onboard("source")
    assert report["stage"] == "introspect"
    assert report["error"] == "introspect failed (RuntimeError)"
    assert "secret" not in report["error"]

    bad_dataset = SimpleNamespace(name=" orders", columns=[], primary_key=[])
    monkeypatch.setattr(onboard_module, "get_connector", lambda name: Connector(datasets=[bad_dataset]))
    report = onboard_module.onboard("source")
    assert report["stage"] == "report"
    assert report["error"].startswith("report failed (")

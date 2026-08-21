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
    monkeypatch.setattr(onboard_module, "get_connector", lambda name: (_ for _ in ()).throw(KeyError(name)))
    report = onboard_module.onboard("missing")
    assert report["ok"] is False
    assert report["stage"] == "resolve"


def test_onboard_reports_connection_exception_and_negative_probe(monkeypatch):
    monkeypatch.setattr(onboard_module, "get_connector", lambda name: Connector(test_error=RuntimeError("offline")))
    assert onboard_module.onboard("source")["stage"] == "connect"

    monkeypatch.setattr(onboard_module, "get_connector", lambda name: Connector(test_result=(False, "denied")))
    report = onboard_module.onboard("source")
    assert report["stage"] == "connect"
    assert report["error"] == "denied"


def test_onboard_reports_introspection_and_report_shape_failures(monkeypatch):
    monkeypatch.setattr(
        onboard_module,
        "get_connector",
        lambda name: Connector(introspect_error=RuntimeError("schema timeout")),
    )
    assert onboard_module.onboard("source")["stage"] == "introspect"

    bad_dataset = SimpleNamespace(name=" orders", columns=[], primary_key=[])
    monkeypatch.setattr(onboard_module, "get_connector", lambda name: Connector(datasets=[bad_dataset]))
    assert onboard_module.onboard("source")["stage"] == "report"

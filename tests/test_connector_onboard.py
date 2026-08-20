"""Connector onboarding failure and readiness reporting."""

from dm.connect.base import ColumnDef, DatasetDef
import dm.connect.onboard as onboard_module


class _Connector:
    def __init__(self, *, ok=True, message="ok", datasets=None, error=None):
        self.ok = ok
        self.message = message
        self.datasets = datasets or []
        self.error = error

    def test_connection(self):
        return self.ok, self.message

    def introspect(self):
        if self.error is not None:
            raise self.error
        return self.datasets


def test_onboard_labels_connection_failures(monkeypatch):
    connector = _Connector(ok=False, message="connection refused")
    monkeypatch.setattr(onboard_module, "get_connector", lambda name: connector)

    report = onboard_module.onboard("erp")

    assert report == {
        "source": "erp",
        "ok": False,
        "stage": "connect",
        "error": "connection refused",
    }


def test_onboard_labels_introspection_failures(monkeypatch):
    connector = _Connector(error=RuntimeError("metadata denied"))
    monkeypatch.setattr(onboard_module, "get_connector", lambda name: connector)

    report = onboard_module.onboard("erp")

    assert report["source"] == "erp"
    assert report["ok"] is False
    assert report["stage"] == "introspect"
    assert report["error"] == "metadata denied"


def test_onboard_reports_dataset_shape(monkeypatch):
    datasets = [
        DatasetDef(
            name="orders",
            columns=[ColumnDef("id", "integer"), ColumnDef("status", "varchar")],
            primary_key=["id"],
        )
    ]
    connector = _Connector(datasets=datasets)
    monkeypatch.setattr(onboard_module, "get_connector", lambda name: connector)
    monkeypatch.setattr(onboard_module, "ONTOLOGY", {})

    report = onboard_module.onboard("erp")

    assert report["ok"] is True
    assert report["n_tables"] == 1
    assert report["datasets"] == [
        {"name": "orders", "columns": 2, "pk": ["id"], "mapped": False}
    ]

from datetime import datetime, timezone
import sys
from types import ModuleType

from dm.agent import core


def test_agent_trace_records_use_aware_utc_timestamps(monkeypatch):
    records = []
    monkeypatch.setenv("DM_AGENT_IMPL", "langgraph")
    monkeypatch.setattr(core, "append_log", lambda name, record: records.append((name, record)))
    fake_graph = ModuleType("dm.agent.graph")
    fake_graph.run_graph = lambda *_args, **_kwargs: "done"
    monkeypatch.setitem(sys.modules, "dm.agent.graph", fake_graph)

    result = core.run_agent("health check", channel="test")

    assert result["answer"] == "done"
    assert records
    for name, record in records:
        assert name == "agent_session"
        parsed = datetime.fromisoformat(record["ts"])
        assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)

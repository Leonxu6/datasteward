from scripts.audit_asyncio_event_loop_policy import audit_source


def test_event_loop_policy_audit_allows_loop_lookup():
    assert audit_source("asyncio.get_running_loop()\n") == []


def test_event_loop_policy_audit_reports_global_policy_changes():
    assert audit_source("asyncio.set_event_loop_policy(policy)\n") == ["asyncio.set_event_loop_policy() mutates process async policy on line 1"]

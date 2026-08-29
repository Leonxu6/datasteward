import re

from dm.tools import principal


def test_generated_session_ids_include_utc_time_and_entropy(monkeypatch):
    monkeypatch.setattr(principal.secrets, "token_hex", lambda size: "a1b2c3d4e5f6")
    session_id = principal._generated_session_id()
    assert re.fullmatch(r"mcp-\d{8}T\d{12}Z-a1b2c3d4e5f6", session_id)


def test_principal_from_env_generates_session_when_missing(monkeypatch):
    monkeypatch.delenv("DM_SESSION_ID", raising=False)
    monkeypatch.setattr(principal, "_generated_session_id", lambda: "mcp-generated")
    assert principal.principal_from_env().session_id == "mcp-generated"


def test_principal_from_env_preserves_explicit_session(monkeypatch):
    monkeypatch.setenv("DM_SESSION_ID", "session-123")
    monkeypatch.setattr(principal, "_generated_session_id", lambda: (_ for _ in ()).throw(AssertionError("not used")))
    assert principal.principal_from_env().session_id == "session-123"

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from dm.tools import _isolation


@pytest.mark.parametrize("value", [True, 0, -1, 601, 1.5, "30"])
def test_timeout_seconds_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        _isolation._timeout_seconds(value)


def test_run_isolated_rejects_timeout_before_spawning():
    with patch.object(_isolation.subprocess, "run") as run:
        with pytest.raises(ValueError):
            _isolation.run_isolated("dm.example", [], 0)
    run.assert_not_called()


def test_arun_isolated_rejects_timeout_before_spawning():
    async def exercise():
        with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as create:
            with pytest.raises(ValueError):
                await _isolation.arun_isolated("dm.example", [], True)
        create.assert_not_awaited()

    asyncio.run(exercise())


def test_parse_dmjson_accepts_one_standard_json_frame():
    assert _isolation._parse_dmjson('noise\nDMJSON:{"ok":true,"n":2}\n', "") == {"ok": True, "n": 2}


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_parse_dmjson_rejects_nonstandard_json_numbers(constant):
    with pytest.raises(RuntimeError, match="DMJSON"):
        _isolation._parse_dmjson(f'DMJSON:{{"value":{constant}}}\n', "")


def test_parse_dmjson_rejects_duplicate_object_keys():
    with pytest.raises(RuntimeError, match="DMJSON"):
        _isolation._parse_dmjson('DMJSON:{"ok":true,"ok":false}\n', "")


def test_parse_dmjson_rejects_multiple_protocol_frames():
    with pytest.raises(RuntimeError, match="多个 DMJSON"):
        _isolation._parse_dmjson('DMJSON:{"a":1}\nDMJSON:{"a":2}\n', "")


def test_parse_dmjson_rejects_oversized_protocol_frame(monkeypatch):
    monkeypatch.setattr(_isolation, "_MAX_PROTOCOL_LINE_CHARS", 20)
    with pytest.raises(RuntimeError, match="大小上限"):
        _isolation._parse_dmjson('DMJSON:{"payload":"xxxxxxxx"}\n', "")


def test_stop_and_reap_kills_and_waits_for_child():
    class FakeProcess:
        def __init__(self):
            self.killed = False
            self.waited = False

        def kill(self):
            self.killed = True

        async def wait(self):
            self.waited = True
            return -9

    proc = FakeProcess()
    asyncio.run(_isolation._stop_and_reap(proc))
    assert proc.killed is True
    assert proc.waited is True


def test_stop_and_reap_still_waits_if_process_already_exited():
    class FakeProcess:
        def __init__(self):
            self.waited = False

        def kill(self):
            raise ProcessLookupError

        async def wait(self):
            self.waited = True
            return 0

    proc = FakeProcess()
    asyncio.run(_isolation._stop_and_reap(proc))
    assert proc.waited is True

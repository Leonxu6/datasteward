import json

import pytest

from dm.kg import graph_cli


def test_parse_args_accepts_json_objects():
    assert graph_cli._parse_args('{"entity_id":"M0001","limit":3}') == {"entity_id": "M0001", "limit": 3}


@pytest.mark.parametrize("raw", ["[1,2]", '"text"', "null", "true", "1"])
def test_parse_args_rejects_non_object_json(raw):
    with pytest.raises(ValueError, match="JSON 对象"):
        graph_cli._parse_args(raw)


def test_parse_args_redacts_json_decoder_details():
    secret = "super-secret-token"
    with pytest.raises(ValueError, match="必须是合法 JSON") as exc_info:
        graph_cli._parse_args('{"token":"' + secret)
    assert secret not in str(exc_info.value)


def test_emit_uses_strict_json(capsys):
    graph_cli._emit({"ok": True, "items": [1, 2]})
    line = capsys.readouterr().out.strip()
    assert line.startswith("DMJSON:")
    assert json.loads(line.removeprefix("DMJSON:")) == {"ok": True, "items": [1, 2]}


def test_emit_rejects_nonstandard_json_numbers():
    with pytest.raises(ValueError):
        graph_cli._emit({"value": float("nan")})

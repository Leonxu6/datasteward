import json
import sys

import pytest

from dm.docs import search_cli


def test_search_cli_emits_one_standard_dmjson_frame(monkeypatch, capsys):
    from dm.docs import search

    monkeypatch.setattr(search, "search", lambda query, top_k: [{"title": "规格", "score": 0.5}])
    monkeypatch.setattr(sys, "argv", ["search_cli", "轴承", "3"])

    search_cli.main()

    output = capsys.readouterr().out.strip()
    assert output.startswith("DMJSON:")
    assert json.loads(output.removeprefix("DMJSON:")) == [{"title": "规格", "score": 0.5}]


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_search_cli_rejects_nonstandard_json_numbers(monkeypatch, number):
    from dm.docs import search

    monkeypatch.setattr(search, "search", lambda query, top_k: [{"score": number}])
    monkeypatch.setattr(sys, "argv", ["search_cli", "query", "5"])

    with pytest.raises(ValueError):
        search_cli.main()

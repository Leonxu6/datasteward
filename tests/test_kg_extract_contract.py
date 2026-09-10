import json

import pytest

from dm.kg import build


def _chat_result(monkeypatch, payload):
    from dm import llm

    monkeypatch.setattr(llm, "chat", lambda *args, **kwargs: payload)


def test_llm_extract_accepts_one_well_formed_triple(monkeypatch):
    _chat_result(monkeypatch, json.dumps({
        "triples": [{
            "s": "M0001",
            "s_type": "Material",
            "r": "PROCESSED_ON",
            "o": "CNC-08",
            "o_type": "Equipment",
            "note": "工艺卡指定设备",
        }]
    }, ensure_ascii=False))

    assert build._llm_extract("DOC-1", "工艺卡", "正文") == [{
        "s": "M0001",
        "s_type": "Material",
        "r": "PROCESSED_ON",
        "o": "CNC-08",
        "o_type": "Equipment",
        "note": "工艺卡指定设备",
    }]


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_llm_extract_rejects_nonstandard_json_constants(monkeypatch, constant):
    _chat_result(monkeypatch, f'{{"triples":[{{"s":"M1","s_type":"Material","r":"REL","o":"E1","o_type":"Equipment","note":{constant}}}]}}')
    assert build._llm_extract("DOC-1", "title", "body") == []


def test_llm_extract_rejects_duplicate_json_keys(monkeypatch):
    _chat_result(monkeypatch, '{"triples":[],"triples":[{"s":"M1"}]}')
    assert build._llm_extract("DOC-1", "title", "body") == []


def test_llm_extract_filters_malformed_triples(monkeypatch):
    _chat_result(monkeypatch, json.dumps({
        "triples": [
            {"s": "M1", "s_type": "Material", "r": "USES", "o": "E1", "o_type": "Equipment"},
            {"s": "M2", "s_type": "Material", "r": "USES", "o": "", "o_type": "Equipment"},
            "not-an-object",
        ]
    }))
    triples = build._llm_extract("DOC-1", "title", "body")
    assert len(triples) == 1
    assert triples[0]["s"] == "M1"


def test_llm_extract_rejects_oversized_payload(monkeypatch):
    monkeypatch.setattr(build, "_MAX_LLM_OUTPUT_CHARS", 20)
    _chat_result(monkeypatch, '{"triples":[]}' + "x" * 50)
    assert build._llm_extract("DOC-1", "title", "body") == []


def test_dynamic_graph_identifiers_stay_ascii_and_syntax_safe():
    assert build._safe_label("Material") == "Material"
    assert build._safe_label("123") == "Entity"
    assert build._safe_label("材料") == "Entity"
    assert build._safe_relation_type("processed-on") == "PROCESSED_ON"
    assert build._safe_relation_type("123") == "REL"

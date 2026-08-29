import pytest

from dm.kg import query


def test_find_related_validates_entity_and_bounds_before_driver(monkeypatch):
    monkeypatch.setattr(query, "run_read", lambda *args, **kwargs: [])
    for entity in (None, "", " id", "id\n"):
        with pytest.raises(ValueError):
            query.find_related(entity)
    for value in (True, 0, 5, "2"):
        with pytest.raises(ValueError):
            query.find_related("customer:1", max_hops=value)
    for value in (True, 0, 101, "30"):
        with pytest.raises(ValueError):
            query.find_related("customer:1", limit=value)


def test_find_related_keeps_valid_limits_and_parameters(monkeypatch):
    calls = []
    monkeypatch.setattr(query, "run_read", lambda cypher, **params: calls.append((cypher, params)) or [])
    result = query.find_related("customer:1", max_hops=4, limit=100)
    assert result["max_hops"] == 4
    assert "[*1..4]" in calls[0][0]
    assert "LIMIT 100" in calls[0][0]
    assert calls[0][1] == {"id": "customer:1"}


def test_impact_path_rejects_modified_or_unsafe_labels(monkeypatch):
    monkeypatch.setattr(query, "run_read", lambda *args, **kwargs: pytest.fail("driver should not be called"))
    for target in ("", " SalesOrder", "Sales-Order", "Sales Order", "9Type", "A" * 65):
        with pytest.raises(ValueError):
            query.impact_path("customer:1", target)


def test_impact_path_uses_validated_label_verbatim(monkeypatch):
    calls = []
    monkeypatch.setattr(query, "run_read", lambda cypher, **params: calls.append((cypher, params)) or [])
    result = query.impact_path("customer:1", "SalesOrder", max_hops=6, limit=50)
    assert result["target_type"] == "SalesOrder"
    assert "(b:SalesOrder)" in calls[0][0]
    assert "[*1..6]" in calls[0][0]


def test_restricted_cypher_rejects_non_text_oversized_and_multiple_statements(monkeypatch):
    monkeypatch.setattr(query, "run_read", lambda *args, **kwargs: pytest.fail("driver should not be called"))
    with pytest.raises(ValueError):
        query.restricted_cypher(None)
    with pytest.raises(ValueError):
        query.restricted_cypher("M" * 20_001)
    assert "一次只允许一条" in query.restricted_cypher("MATCH (n) RETURN n; MATCH (m) RETURN m")["error"]


def test_restricted_cypher_rejects_procedure_calls_and_writes(monkeypatch):
    monkeypatch.setattr(query, "run_read", lambda *args, **kwargs: pytest.fail("driver should not be called"))
    for cypher in (
        "CREATE (n)",
        "MATCH (n) DELETE n",
        "CALL db.labels() YIELD label RETURN label",
        "CALL apoc.help('x') YIELD type RETURN type",
    ):
        assert "已拒绝" in query.restricted_cypher(cypher)["error"]


def test_restricted_cypher_adds_a_validated_limit(monkeypatch):
    calls = []
    monkeypatch.setattr(query, "run_read", lambda cypher, **params: calls.append(cypher) or [{"id": 1}])
    result = query.restricted_cypher("MATCH (n) RETURN n", limit=25)
    assert calls == ["MATCH (n) RETURN n LIMIT 25"]
    assert result["count"] == 1
    for value in (True, 0, 201, "50"):
        with pytest.raises(ValueError):
            query.restricted_cypher("MATCH (n) RETURN n", limit=value)

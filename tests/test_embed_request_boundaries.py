import pytest

from dm.docs import embed


def test_hash_embedding_accepts_text_and_generators(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    assert len(embed.embed("hello")) == 1
    vectors = embed.embed((text for text in ["hello", "world"]))
    assert len(vectors) == 2
    assert all(len(vector) == embed.DIM for vector in vectors)


def test_embedding_rejects_scalar_collections_and_empty_batches(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    for value in (None, b"hello", {"hello": 1}, [], 7):
        with pytest.raises(ValueError):
            embed.embed(value)


def test_embedding_rejects_invalid_text_items_before_model_use(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    for values in ([""], ["   "], [7], ["bad\x00text"]):
        with pytest.raises(ValueError):
            embed.embed(values)


def test_embedding_batch_and_text_sizes_are_bounded(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    monkeypatch.setattr(embed, "_MAX_BATCH", 2)
    monkeypatch.setattr(embed, "_MAX_TEXT_CHARS", 3)
    with pytest.raises(ValueError, match="batch"):
        embed.embed(["a", "b", "c"])
    with pytest.raises(ValueError, match="characters"):
        embed.embed(["abcd"])


def test_embedding_query_mode_requires_a_boolean(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    for value in (1, "true", None):
        with pytest.raises(ValueError, match="is_query"):
            embed.embed(["hello"], is_query=value)

import os
from pathlib import Path
import subprocess
import sys

import pytest

from dm.docs import embed


def test_embedding_import_does_not_mutate_huggingface_environment():
    env = os.environ.copy()
    env.pop("HF_HUB_DISABLE_SYMLINKS", None)
    env.pop("HF_HUB_DISABLE_SYMLINKS_WARNING", None)
    source_root = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (source_root, env.get("PYTHONPATH"))))
    code = (
        "import os; import dm.docs.embed; "
        "print(os.environ.get('HF_HUB_DISABLE_SYMLINKS', 'missing')); "
        "print(os.environ.get('HF_HUB_DISABLE_SYMLINKS_WARNING', 'missing'))"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
        env=env,
    )

    assert result.stdout.splitlines() == ["missing", "missing"]


def test_hash_embedding_accepts_text_and_generators(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    assert len(embed.embed("hello")) == 1
    vectors = embed.embed((text for text in ["hello", "world"]))
    assert len(vectors) == 2
    assert all(len(vector) == embed.DIM for vector in vectors)


def test_embedding_backend_must_be_explicitly_supported(monkeypatch):
    for value in ("", " hash", "hash ", "HASH", "unknown"):
        monkeypatch.setenv("DM_EMBED_BACKEND", value)
        with pytest.raises(ValueError, match="embedding backend"):
            embed.embed(["hello"])


def test_embedding_rejects_scalar_collections_and_empty_batches(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    for value in (None, b"hello", {"hello": 1}, [], 7):
        with pytest.raises(ValueError):
            embed.embed(value)


def test_embedding_rejects_invalid_text_items_before_model_use(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    for values in ([""], ["   "], [7], ["bad\x00text"], ["bad\u200dtext"], ["bad\ud800text"]):
        with pytest.raises(ValueError):
            embed.embed(values)


def test_embedding_allows_normal_multiline_whitespace(monkeypatch):
    monkeypatch.setenv("DM_EMBED_BACKEND", "hash")
    vectors = embed.embed(["first line\nsecond line", "tab\tseparated"])
    assert len(vectors) == 2


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

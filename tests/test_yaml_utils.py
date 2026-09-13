import pytest
import yaml

from dm.yaml_utils import safe_load_unique


def test_safe_load_unique_parses_nested_mappings():
    assert safe_load_unique("service:\n  host: localhost\n  port: 8080\n") == {
        "service": {"host": "localhost", "port": 8080}
    }


@pytest.mark.parametrize(
    "document",
    [
        "mode: safe\nmode: unsafe\n",
        "service:\n  timeout: 5\n  timeout: 30\n",
    ],
)
def test_safe_load_unique_rejects_duplicate_mapping_keys(document):
    with pytest.raises(ValueError, match="duplicate YAML mapping key"):
        safe_load_unique(document)


def test_safe_load_unique_keeps_safe_loader_tag_restrictions():
    with pytest.raises(yaml.constructor.ConstructorError):
        safe_load_unique("!!python/object/apply:os.system ['echo unsafe']\n")


def test_safe_load_unique_rejects_unbounded_input_and_bad_limits():
    with pytest.raises(ValueError, match="at most 8 characters"):
        safe_load_unique("a: 123456789\n", max_chars=8)
    for limit in (0, -1, True, 1.5):
        with pytest.raises(ValueError, match="positive integer"):
            safe_load_unique("a: 1\n", max_chars=limit)


def test_safe_load_unique_caps_caller_requested_budget():
    with pytest.raises(ValueError, match="max_chars must be at most 1000000"):
        safe_load_unique("a: 1\n", max_chars=1_000_001)


def test_safe_load_unique_requires_text():
    with pytest.raises(ValueError, match="must be text"):
        safe_load_unique({"a": 1})

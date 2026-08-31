import pytest

from dm.tools.identity import normalize_channel


def test_channel_labels_keep_machine_safe_ascii():
    assert normalize_channel("mcp_v2") == "mcp_v2"
    with pytest.raises(ValueError, match="ASCII"):
        normalize_channel("渠道")

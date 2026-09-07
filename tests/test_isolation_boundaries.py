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

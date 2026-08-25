"""pytest 公共夹具：用临时目录做数据/留痕目录，避免依赖/污染真实数据。

必须在 import 任何 dm.* 之前设好 DM_DATA_DIR —— dm.config 在导入时读取它。

两档测试：
- 纯单元（默认给外部贡献者/CI）：无需任何外部服务，`pytest -m "not integration and not stack"`。
- stack 用例：需要可达的 StarRocks/Postgres 栈（`docker compose -f deploy/docker-compose.yml up -d`）。
  栈不可达时自动跳过，绝不报错。
"""
import os
import socket
import sys
import tempfile
from pathlib import Path

# Repository-local maintenance tooling lives outside the installable ``src`` tree.
# Ensure those modules are importable even when pytest is launched through its
# console entry point, whose sys.path does not necessarily include the checkout.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 早于 dm 导入：把数据目录指向一个临时目录
_TMP = Path(tempfile.mkdtemp(prefix="dm-test-"))
os.environ.setdefault("DM_DATA_DIR", str(_TMP))

import pytest  # noqa: E402

_REACHABLE = None


def _stack_reachable() -> bool:
    """探测 StarRocks 是否可达（进程内缓存，只探一次）。"""
    global _REACHABLE
    if _REACHABLE is None:
        from dm.config import WH_HOST, WH_PORT
        try:
            with socket.create_connection((WH_HOST, WH_PORT), timeout=2):
                _REACHABLE = True
        except OSError:
            _REACHABLE = False
    return _REACHABLE


def pytest_collection_modifyitems(config, items):
    """栈不可达时自动跳过 stack 用例——外部贡献者裸机 `pytest` 不炸。"""
    if _stack_reachable():
        return
    skip = pytest.mark.skip(
        reason="StarRocks 不可达；`docker compose -f deploy/docker-compose.yml up -d` 后可跑 stack 用例")
    for item in items:
        if "stack" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session", autouse=True)
def warehouse(request):
    """会话级：仅当本次会话真的要跑 stack 用例时，才建一份合成数仓。"""
    items = getattr(request.session, "items", [])
    needs = any("stack" in i.keywords and not i.get_closest_marker("skip") for i in items)
    if needs:
        from dm.warehouse.load import main as load_main
        load_main()
    yield

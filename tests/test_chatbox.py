"""端到端：聊天框点『提问』→ 真实跑智能体 → 显示答案（需要 claude，标 integration）。"""

from importlib.resources import files

import pytest
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.stack  # 需要可达的 StarRocks/Postgres 栈；不可达自动跳过

APP = str(files("dm.app") / "app.py")


@pytest.mark.integration
def test_chatbox_drives_agent():
    at = AppTest.from_file(APP).run(timeout=60)
    at.sidebar.radio[0].set_value("💬 智能体问答").run(timeout=60)
    at.text_input[0].set_value("数据仓库里一共有多少种物料？").run(timeout=60)
    btns = [b for b in at.button if b.label == "提问"]
    assert btns, "未找到『提问』按钮"
    btns[0].click().run(timeout=240)
    assert not at.exception, f"聊天框异常: {list(at.exception)}"
    mds = [str(m.value) for m in at.markdown]
    assert any(("50" in m or "物料" in m) for m in mds)

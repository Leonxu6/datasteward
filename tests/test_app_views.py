"""管理平台代表性视图都能渲染（headless AppTest，确定性）——与 app.py 的 MODULES 标签保持同步。"""
from importlib.resources import files

import pytest
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.stack  # 需要可达的 StarRocks/Postgres 栈；不可达自动跳过

APP = str(files("dm.app") / "app.py")
VIEWS = ["🗄️ 数据仓库", "🛡️ 访问治理", "🧠 智能体", "✅ 质量 Eval", "📇 数据目录", "📏 指标字典"]


@pytest.mark.parametrize("view", VIEWS)
def test_view_renders(view):
    at = AppTest.from_file(APP).run(timeout=90)
    at.sidebar.radio[0].set_value(view).run(timeout=90)
    assert not at.exception, f"{view} 渲染异常: {list(at.exception)}"

"""`dm-app` 入口：在打包内的 app.py 上启动 Streamlit。

Streamlit 需要一个文件路径（不是模块），所以用 importlib.resources 定位包内 app.py，
再交给 streamlit 的 CLI 运行。等价于：streamlit run <包内>/app.py
"""
import sys
from importlib.resources import files


def main():
    app_path = str(files("dm.app") / "app.py")
    sys.argv = ["streamlit", "run", app_path, *sys.argv[1:]]
    from streamlit.web import cli as stcli
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()

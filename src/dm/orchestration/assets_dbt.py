"""dbt 模型 → Dagster 资产（dagster-dbt 官方集成）。

- 每个 dbt 模型/测试都成为可观测资产（血缘/状态/重跑免费获得）；
- raw_u8__* 源映射到 assets_u8 的资产键 → U8 抽取与 DW 分层在同一张资产图上连通。
manifest 由 DbtProject 在启动时准备（容器内构建镜像时已 dbt parse 预热）。
"""
import os
import shutil
import sys
from pathlib import Path

from dagster import AssetExecutionContext, AssetKey
from dagster_dbt import DagsterDbtTranslator, DbtCliResource, DbtProject, dbt_assets

DBT_DIR = Path(os.environ.get("DM_DBT_DIR") or
               Path(__file__).resolve().parents[3] / "transform" / "dbt")


def _dbt_exe() -> str:
    """dbt 可执行文件：PATH 优先；否则取当前解释器旁的 Scripts/bin（本地 venv 场景）。"""
    found = shutil.which("dbt")
    if found:
        return found
    cand = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    return str(cand) if cand.exists() else "dbt"

dbt_project = DbtProject(project_dir=DBT_DIR, profiles_dir=DBT_DIR)
dbt_project.prepare_if_dev()

_MANIFEST = dbt_project.manifest_path
if not _MANIFEST.exists():
    # 兜底：镜像/环境缺 manifest 时现场 parse（离线，不连库）——绝不让 Definitions 加载失败
    import subprocess
    subprocess.run([_dbt_exe(), "parse", "--profiles-dir", str(DBT_DIR), "--no-partial-parse"],
                   cwd=DBT_DIR, check=True, timeout=300)


class DmDbtTranslator(DagsterDbtTranslator):
    def get_asset_key(self, dbt_resource_props):
        # U8 源表与 assets_u8 的资产键对齐（同键 → 图上自动连边）
        if dbt_resource_props["resource_type"] == "source" and dbt_resource_props["source_name"] == "u8":
            return AssetKey(dbt_resource_props["name"])
        return super().get_asset_key(dbt_resource_props)


@dbt_assets(manifest=_MANIFEST, dagster_dbt_translator=DmDbtTranslator())
def dm_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


dbt_resource = DbtCliResource(project_dir=DBT_DIR, profiles_dir=str(DBT_DIR), dbt_executable=_dbt_exe())

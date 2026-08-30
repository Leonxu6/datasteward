"""编排作业：U8+DW 全链路 / 文档+图谱重建 / eval 夜跑。"""
from dagster import AssetSelection, In, Nothing, define_asset_job, job, op

from dm.orchestration.cli_argv import temporary_argv

# ---- 资产作业：U8 抽取 → dbt 分层（同一张资产图，Dagster 自动按依赖排序）----
job_u8_dbt = define_asset_job(
    name="job_u8_dbt",
    selection=AssetSelection.all(),
    description="U8 增量抽取 → dbt build（ODS→DWD→DWS→ADS + tests）全链路",
)


# ---- 文档库 + 知识图谱重建（按需手动触发；LLM 抽取走网关）----
@op(description="重建 RAG 文档库（合成文档 → 本地嵌入 → pgvector）")
def op_docs_build():
    from dm.docs.index import main as docs_main

    with temporary_argv(["dm-docs", "build"]):
        docs_main()


@op(ins={"after": In(Nothing)}, description="重建知识图谱（FK 骨架 + LLM 文档关系抽取 → Neo4j）")
def op_kg_build():
    from dm.kg.build import main as kg_main

    with temporary_argv(["dm-kg", "build"]):
        kg_main()


@job(description="文档库 + 知识图谱重建（文档变更后手动触发）")
def job_docs_kg_rebuild():
    op_kg_build(after=op_docs_build())


# ---- eval 夜跑：全量用例真实调用智能体 + 判分，结果落 eval_run.jsonl（质量页可见）----
@op(description="跑全量 eval 用例（真实调用 LangGraph 智能体）")
def op_eval_all():
    from dm.eval.run_eval import main as eval_main

    eval_main()


@job(description="eval 夜跑（02:00）：通过率基线守护")
def job_eval_nightly():
    op_eval_all()

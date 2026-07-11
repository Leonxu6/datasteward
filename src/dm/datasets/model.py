"""数据集分层（raw / refined）+ Transform 注册表。

对标 Palantir：连接器抽数 →【raw 原样落地】→ transform（清洗/类型规整/去重/口径统一）→【refined 供本体与分析】。
每个 transform 声明 inputs/outputs（+ 列映射）→ 自动登记血缘（见 pipeline/lineage.py）。

我们栈的落地（PoC v0）：
- **refined 数据集** = 现有 19 张 StarRocks 表（schema.py 派生），供本体/分析/智能体。
- **raw 数据集** = 每张表对应的原始落地 `raw__<table>`（连接器从 PG 影子源抽取原样落地）。
- **transform** `refine__<table>`：raw → refined 的清洗（v0 为 1:1 列直通，列级血缘留痕）。

单一真相源仍是 schema.py；本层是"数据流视角"的派生，与 ontology（语义视角）互补、不重复。
"""
from dataclasses import dataclass, field
from enum import Enum

from dm.config import DW_SCHEMA
from dm.ontology.model import BASE_TYPE_MAP
from dm.schema import TABLES


class Tier(str, Enum):
    RAW = "raw"
    REFINED = "refined"
    DW = "dw"          # dbt 产出层（DWD/DWS/ADS，落 DW_SCHEMA 库，默认 dm_dw）


@dataclass
class Dataset:
    name: str
    tier: str                       # raw / refined
    backing: str                    # 落地位置（StarRocks 表名 / raw 落地表名）
    columns: list = field(default_factory=list)   # [(col, base_type)]
    source: str = None              # raw 数据集的来源（源名，如 pg_shadow）
    transform: str = None           # refined 数据集的产出 transform 名
    markings: list = field(default_factory=list)  # 显式打标（会沿血缘向下游传播）
    description: str = ""

    def col_names(self):
        return [c[0] for c in self.columns]


@dataclass
class Transform:
    name: str
    kind: str                       # extract / clean / refine
    inputs: list = field(default_factory=list)    # 输入数据集名
    outputs: list = field(default_factory=list)   # 输出数据集名
    column_map: dict = field(default_factory=dict)  # 输出列 -> [输入列]（列级血缘）
    description: str = ""


def _build():
    """从 schema.py 构建 raw + refined 数据集与 refine transform 注册表。"""
    datasets: dict = {}
    transforms: dict = {}
    for t in TABLES:
        name = t["name"]
        cols = [(c[0], BASE_TYPE_MAP.get(c[1].upper(), "String")) for c in t["columns"]]
        raw_name = f"raw__{name}"
        datasets[raw_name] = Dataset(
            name=raw_name, tier=Tier.RAW.value, backing=raw_name, columns=cols,
            source="pg_shadow", description=f"{t['cn']} 原始落地（连接器抽取，未清洗）")
        datasets[name] = Dataset(
            name=name, tier=Tier.REFINED.value, backing=name, columns=cols,
            transform=f"refine__{name}", description=f"{t['cn']}（清洗整合，供本体/分析）")
        transforms[f"refine__{name}"] = Transform(
            name=f"refine__{name}", kind="refine", inputs=[raw_name], outputs=[name],
            column_map={c[0]: [c[0]] for c in t["columns"]},   # v0：列直通（1:1）
            description=f"清洗/类型规整/口径统一 → {t['cn']}")
    _add_u8(datasets)
    _add_dbt(datasets, transforms)
    return datasets, transforms


def _add_u8(datasets: dict):
    """U8 ODS 数据集：raw_u8__*（源 u8_erp，打 U8 Marking——沿血缘传播到全部下游）。"""
    from dm.connect.u8_mapping import U8_TABLE_MAP, ods_name
    for m in U8_TABLE_MAP:
        name = ods_name(m["u8"])
        datasets[name] = Dataset(
            name=name, tier=Tier.RAW.value, backing=name, columns=[],
            source="u8_erp", markings=["U8"],
            description=f"U8 {m['cn']}（{m['u8']}）原样落地（dm-u8 批抽，游标 {m['cursor'] or '全量刷'}）")


def _add_dbt(datasets: dict, transforms: dict):
    """dbt 产出层并入数据集/血缘注册表（读 manifest.json，缺失时静默跳过）。

    dbt 模型 → Dataset(tier=dw)；每个模型一个 Transform(kind=dbt)，inputs=上游
    （source→同名 ODS 数据集 / 上游模型 / seed）。Marking 沿这些边继续传播——
    raw_u8__* 的 U8 标自动继承到 DWD/DWS/ADS。"""
    import json
    import os
    from pathlib import Path
    dbt_dir = Path(os.environ.get("DM_DBT_DIR") or
                   Path(__file__).resolve().parents[3] / "transform" / "dbt")
    mf = dbt_dir / "target" / "manifest.json"
    if not mf.exists():
        return
    try:
        m = json.loads(mf.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return

    def _ref(unique_id: str) -> str:
        # source.<proj>.<srcname>.<table> → table；model/seed.<proj>.<name> → name
        parts = unique_id.split(".")
        return parts[-1]

    nodes = m.get("nodes", {})
    for uid, nd in nodes.items():
        if nd.get("resource_type") == "seed":
            name = nd["name"]
            if name not in datasets:
                datasets[name] = Dataset(name=name, tier=Tier.DW.value, backing=f"{DW_SCHEMA}.{name}",
                                         description=nd.get("description") or "dbt seed")
    for uid, nd in nodes.items():
        if nd.get("resource_type") != "model":
            continue
        name = nd["name"]
        layer = (nd.get("fqn") or ["", ""])[1] if len(nd.get("fqn") or []) > 2 else "dw"
        datasets[name] = Dataset(
            name=name, tier=Tier.DW.value, backing=f"{DW_SCHEMA}.{name}",
            transform=f"dbt__{name}",
            description=(nd.get("description") or f"dbt 模型（{layer} 层）"))
        parents = [_ref(p) for p in m.get("parent_map", {}).get(uid, [])]
        parents = [p for p in parents if p in datasets or p == name]
        transforms[f"dbt__{name}"] = Transform(
            name=f"dbt__{name}", kind="dbt", inputs=[p for p in parents if p != name],
            outputs=[name], description=f"dbt build → {DW_SCHEMA}.{name}")


DATASETS, TRANSFORMS = _build()


def datasets(tier: str = None) -> list:
    if tier:
        return [d for d in DATASETS.values() if d.tier == tier]
    return list(DATASETS.values())


def get_dataset(name: str) -> Dataset:
    return DATASETS.get(name)


def transforms() -> list:
    return list(TRANSFORMS.values())

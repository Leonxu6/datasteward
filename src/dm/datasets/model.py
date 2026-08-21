"""数据集分层（raw / refined / dw）+ Transform 注册表。

连接器抽数 → raw → transform → refined；dbt manifest 若存在则把 DWD/DWS/ADS
模型并入同一数据集/血缘注册表。manifest 解析采用防御式 helper，损坏或部分无效的
节点不会让整个数据目录在导入时崩溃。
"""
from dataclasses import dataclass, field
from enum import Enum

from dm.config import DW_SCHEMA
from dm.datasets.dbt_manifest import iter_nodes, load_manifest, model_layer, parent_names
from dm.ontology.model import BASE_TYPE_MAP
from dm.schema import TABLES


class Tier(str, Enum):
    RAW = "raw"
    REFINED = "refined"
    DW = "dw"


@dataclass
class Dataset:
    name: str
    tier: str
    backing: str
    columns: list = field(default_factory=list)
    source: str = None
    transform: str = None
    markings: list = field(default_factory=list)
    description: str = ""

    def col_names(self):
        return [column[0] for column in self.columns]


@dataclass
class Transform:
    name: str
    kind: str
    inputs: list = field(default_factory=list)
    outputs: list = field(default_factory=list)
    column_map: dict = field(default_factory=dict)
    description: str = ""


def _build():
    """从 schema.py 构建 raw + refined，并按需合并 U8 与 dbt 数据集。"""
    datasets: dict = {}
    transforms: dict = {}
    for table in TABLES:
        name = table["name"]
        cols = [(column[0], BASE_TYPE_MAP.get(column[1].upper(), "String")) for column in table["columns"]]
        raw_name = f"raw__{name}"
        datasets[raw_name] = Dataset(
            name=raw_name,
            tier=Tier.RAW.value,
            backing=raw_name,
            columns=cols,
            source="pg_shadow",
            description=f"{table['cn']} 原始落地（连接器抽取，未清洗）",
        )
        datasets[name] = Dataset(
            name=name,
            tier=Tier.REFINED.value,
            backing=name,
            columns=cols,
            transform=f"refine__{name}",
            description=f"{table['cn']}（清洗整合，供本体/分析）",
        )
        transforms[f"refine__{name}"] = Transform(
            name=f"refine__{name}",
            kind="refine",
            inputs=[raw_name],
            outputs=[name],
            column_map={column[0]: [column[0]] for column in table["columns"]},
            description=f"清洗/类型规整/口径统一 → {table['cn']}",
        )
    _add_u8(datasets)
    _add_dbt(datasets, transforms)
    return datasets, transforms


def _add_u8(datasets: dict):
    """U8 ODS 数据集：raw_u8__*，源标记沿血缘传播到下游。"""
    from dm.connect.u8_mapping import U8_TABLE_MAP, ods_name

    for mapping in U8_TABLE_MAP:
        name = ods_name(mapping["u8"])
        datasets[name] = Dataset(
            name=name,
            tier=Tier.RAW.value,
            backing=name,
            columns=[],
            source="u8_erp",
            markings=["U8"],
            description=(
                f"U8 {mapping['cn']}（{mapping['u8']}）原样落地"
                f"（dm-u8 批抽，游标 {mapping['cursor'] or '全量刷'}）"
            ),
        )


def _add_dbt(datasets: dict, transforms: dict):
    """将有效 dbt seed/model 节点并入数据集与血缘注册表。"""
    import os
    from pathlib import Path

    dbt_dir = Path(
        os.environ.get("DM_DBT_DIR")
        or Path(__file__).resolve().parents[3] / "transform" / "dbt"
    )
    manifest = load_manifest(dbt_dir / "target" / "manifest.json")
    if manifest is None:
        return

    for _, node in iter_nodes(manifest, resource_type="seed"):
        name = node["name"]
        if name not in datasets:
            datasets[name] = Dataset(
                name=name,
                tier=Tier.DW.value,
                backing=f"{DW_SCHEMA}.{name}",
                description=node.get("description") or "dbt seed",
            )

    for unique_id, node in iter_nodes(manifest, resource_type="model"):
        name = node["name"]
        layer = model_layer(node)
        datasets[name] = Dataset(
            name=name,
            tier=Tier.DW.value,
            backing=f"{DW_SCHEMA}.{name}",
            transform=f"dbt__{name}",
            description=node.get("description") or f"dbt 模型（{layer} 层）",
        )
        parents = [parent for parent in parent_names(manifest, unique_id) if parent in datasets and parent != name]
        transforms[f"dbt__{name}"] = Transform(
            name=f"dbt__{name}",
            kind="dbt",
            inputs=parents,
            outputs=[name],
            description=f"dbt build → {DW_SCHEMA}.{name}",
        )


DATASETS, TRANSFORMS = _build()


def datasets(tier: str = None) -> list:
    if tier:
        return [dataset for dataset in DATASETS.values() if dataset.tier == tier]
    return list(DATASETS.values())


def get_dataset(name: str) -> Dataset | None:
    return DATASETS.get(name)


def transforms() -> list:
    return list(TRANSFORMS.values())

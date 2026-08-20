"""接客户库 onboarding：自省源 schema → 数据集目录 + 就绪报告。

这是"拿到客户库接上即用"的入口：指向一个源（U8/SQL Server、PostgreSQL、文件），自省其
表/列/主键，产出数据集目录，并对照现有 Ontology 给出"就绪报告"（哪些表已有对象模型、
哪些待建模）。真实 U8 到手后配好 DM_SRC_MSSQL_* 环境变量，`dm-connect onboard u8_erp` 即可。

CLI：
  dm-connect list                # 列出已登记的源
  dm-connect test <source>       # 测试连通
  dm-connect onboard <source>    # 自省 + 就绪报告
"""
import sys

from dm.connect.catalog import get_connector, list_sources
from dm.ontology import ONTOLOGY  # 现有对象类型（键为表名）


def onboard(source_name: str) -> dict:
    """自省一个源并对照 Ontology 给出就绪报告。"""
    conn = get_connector(source_name)
    ok, msg = conn.test_connection()
    if not ok:
        return {"source": source_name, "ok": False, "stage": "connect", "error": msg}
    try:
        dsets = conn.introspect()
    except Exception as exc:  # noqa: BLE001
        return {
            "source": source_name,
            "ok": False,
            "stage": "introspect",
            "error": str(exc),
        }
    known = set(ONTOLOGY.keys())
    mapped = [d.name for d in dsets if d.name in known]
    unmapped = [d.name for d in dsets if d.name not in known]
    return {
        "source": source_name, "ok": True, "n_tables": len(dsets),
        "mapped_object_types": mapped, "unmapped_tables": unmapped,
        "readiness": f"{len(mapped)}/{len(dsets)} 表已有对象模型，{len(unmapped)} 表待建模",
        "datasets": [{"name": d.name, "columns": len(d.columns),
                      "pk": d.primary_key, "mapped": d.name in known} for d in dsets],
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "list"

    if cmd == "list":
        print("已登记的源：")
        for s in list_sources():
            print(f"  {s.name:12} type={s.source_type:10} {s.description}")
        return
    if cmd == "test" and len(argv) >= 2:
        ok, msg = get_connector(argv[1]).test_connection()
        print(f"{argv[1]}: {'✅ 连通' if ok else '❌ ' + msg}")
        return
    if cmd == "onboard" and len(argv) >= 2:
        r = onboard(argv[1])
        if not r["ok"]:
            print(f"❌ {argv[1]} 接入失败（{r.get('stage', 'unknown')}）：{r['error']}")
            return
        print(f"=== 接入就绪报告：{r['source']} ===")
        print(f"自省到 {r['n_tables']} 张表；{r['readiness']}")
        print(f"已有对象模型：{', '.join(r['mapped_object_types'][:30])}")
        if r["unmapped_tables"]:
            print(f"待建模：{', '.join(r['unmapped_tables'])}")
        return
    print(__doc__)


if __name__ == "__main__":
    main()

"""接客户库 onboarding：自省源 schema → 数据集目录 + 就绪报告。

CLI：
  dm-connect list
  dm-connect test <source>
  dm-connect onboard <source>
"""
import sys

from dm.connect.catalog import get_connector, list_sources
from dm.connect.readiness import build_readiness_report
from dm.ontology import ONTOLOGY


def onboard(source_name: str) -> dict:
    """自省一个源并对照 Ontology 给出结构化就绪报告。"""
    try:
        conn = get_connector(source_name)
    except Exception as exc:  # noqa: BLE001
        return {"source": source_name, "ok": False, "stage": "resolve", "error": str(exc)}

    try:
        ok, message = conn.test_connection()
    except Exception as exc:  # noqa: BLE001
        return {"source": source_name, "ok": False, "stage": "connect", "error": str(exc)}
    if not ok:
        return {"source": source_name, "ok": False, "stage": "connect", "error": str(message)}

    try:
        datasets = conn.introspect()
    except Exception as exc:  # noqa: BLE001
        return {"source": source_name, "ok": False, "stage": "introspect", "error": str(exc)}

    try:
        return build_readiness_report(source_name, datasets, ONTOLOGY.keys())
    except Exception as exc:  # noqa: BLE001
        return {"source": source_name, "ok": False, "stage": "report", "error": str(exc)}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:]
    cmd = argv[0] if argv else "list"

    if cmd == "list" and len(argv) == 1:
        print("已登记的源：")
        for source in list_sources():
            print(f"  {source.name:12} type={source.source_type:10} {source.description}")
        return 0
    if cmd == "test" and len(argv) == 2:
        try:
            ok, message = get_connector(argv[1]).test_connection()
        except Exception as exc:  # noqa: BLE001
            ok, message = False, str(exc)
        print(f"{argv[1]}: {'✅ 连通' if ok else '❌ ' + str(message)}")
        return 0 if ok else 1
    if cmd == "onboard" and len(argv) == 2:
        report = onboard(argv[1])
        if not report["ok"]:
            print(f"❌ {argv[1]} 接入失败（{report.get('stage', 'unknown')}）：{report['error']}")
            return 1
        print(f"=== 接入就绪报告：{report['source']} ===")
        print(f"自省到 {report['n_tables']} 张表；{report['readiness']}")
        print(f"已有对象模型：{', '.join(report['mapped_object_types'][:30])}")
        if report["unmapped_tables"]:
            print(f"待建模：{', '.join(report['unmapped_tables'])}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

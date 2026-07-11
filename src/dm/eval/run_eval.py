"""Eval 跑批：对每条用例跑智能体 → 自动判分 → 通过率 + 逐条结果（写 logs/eval_run.jsonl）。

判分：确定性题用仓库 SQL 算标准答案自动比对；多步结论用 LLM 评判；越界题查是否正确拒答。
用法: dm-eval（或 python -m dm.eval.run_eval）
"""
import re
import sys
from datetime import datetime
from importlib.resources import files

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dm.warehouse.store import connect_ro, append_log  # noqa: E402
from dm.agent import run_agent  # noqa: E402

REFUSAL_HINTS = ["暂无", "没有该", "无法", "不在", "没有相关", "缺少", "未包含",
                 "查不到", "无此", "不包含", "没有排班", "没有产能",
                 "未提及", "未规定", "没有规定", "未说明", "未注明", "未提到"]


def _truth(sql):
    con = connect_ro()
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def grade_numeric(sql, answer):
    val = _truth(sql)[0][0]
    s = str(int(val)) if isinstance(val, (int, float)) and float(val).is_integer() else str(val)
    found = re.search(r"(?<!\d)" + re.escape(s) + r"(?!\d)", answer.replace(",", "")) is not None
    return found, s


def grade_set(sql, answer):
    items = [str(r[0]) for r in _truth(sql)]
    missing = [x for x in items if not re.search(r"\b" + re.escape(x) + r"\b", answer)]
    return (len(missing) == 0), "{" + ", ".join(items) + "}"


def grade_refusal(answer):
    return any(k in answer for k in REFUSAL_HINTS), "正确拒答（无此数据）"


def grade_contains(needles, answer):
    """RAG 判分：答案（去空格后）须包含全部关键事实串——证明检索到正确文档并据此作答。"""
    norm = answer.replace(" ", "").replace("　", "")
    missing = [n for n in needles if n.replace(" ", "") not in norm]
    exp = "需含: " + "、".join(needles) + (f"（缺: {'、'.join(missing)}）" if missing else "")
    return (len(missing) == 0), exp


def compute_facts(items):
    """用仓库实时算出决定性事实（让 llm_judge 的参考标准随数据自动正确、可复现）。"""
    out = []
    for it in items or []:
        try:
            out.append(f"{it['label']}={_truth(it['sql'])[0][0]}")
        except Exception as e:  # noqa: BLE001
            out.append(f"{it['label']}=(算不出:{e})")
    return "；".join(out)


def grade_llm_judge(question, expected, answer, facts=""):
    ref = expected + (f"\n实时核算事实（来自仓库，权威）：{facts}" if facts else "")
    prompt = (
        "你在给数据问答系统的回答打分，只看主要结论是否与『参考标准』一致。\n"
        f"问题：{question}\n参考标准：{ref}\n系统回答：{answer}\n"
        "若主要结论与参考标准一致，只回 PASS；否则只回 FAIL。")
    from dm.llm import chat
    try:
        out = chat([{"role": "user", "content": prompt}], temperature=0.0, timeout=120).strip().upper()
    except RuntimeError as e:
        return False, f"judge不可用:{str(e)[:20]}"
    # 思考型模型可能带推理前缀——只认结尾判词，且 PASS/FAIL 同现时以 FAIL 为准（保守）
    return ("PASS" in out and "FAIL" not in out), out[-30:]


def main():
    cases = yaml.safe_load((files("dm.eval") / "eval_set.yaml").read_text(encoding="utf-8"))
    run_id = "R" + datetime.now().strftime("%Y%m%d%H%M%S")
    print(f"=== Eval 跑批 {run_id}，共 {len(cases)} 例（每例会真实调用智能体，请耐心等待）===\n")
    passed = 0
    for c in cases:
        # 按用例角色/目的跑（默认管理员+正当目的，避免功能用例被权限/PBAC 屏蔽干扰；
        # 权限用例显式设 role/purpose 触发拦截）
        r = run_agent(c["question"], channel="eval", role=c.get("role", "管理员"),
                      purpose=c.get("purpose", "财务对账"))
        ans, sid = r["answer"], r["session_id"]
        g = c["grader"]
        if g == "numeric":
            ok, exp = grade_numeric(c["truth_sql"], ans)
        elif g == "set":
            ok, exp = grade_set(c["truth_sql"], ans)
        elif g == "refusal":
            ok, exp = grade_refusal(ans)
            exp = c.get("expected", exp)
        elif g == "contains":
            ok, exp = grade_contains(c.get("expected_contains", []), ans)
        elif g == "llm_judge":
            facts = compute_facts(c.get("truth_facts"))
            ok, verdict = grade_llm_judge(c["question"], c.get("expected", ""), ans, facts)
            exp = c.get("expected", "") + (f"  [核算:{facts}]" if facts else "") + f"  [判:{verdict}]"
        else:
            ok, exp = False, "unknown grader"
        passed += int(ok)
        append_log("eval_run", {
            "run_id": run_id, "case_id": c["id"], "category": c["category"],
            "question": c["question"], "expected": str(exp), "got": ans[:1200],
            "grader": g, "passed": bool(ok), "session_id": sid,
            "ts": datetime.now().isoformat(timespec="seconds")})
        mark = "✅PASS" if ok else "❌FAIL"
        print(f'  [{mark}] {c["id"]:3} {c["category"]:12}/{g:9} 期望≈{str(exp)[:34]}')
    print(f"\n=== 通过 {passed}/{len(cases)}  ({passed / len(cases) * 100:.0f}%)  run_id={run_id} ===")


if __name__ == "__main__":
    main()

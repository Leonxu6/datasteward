"""Run repository eval cases against the agent and persist bounded results."""
from __future__ import annotations

import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from importlib.resources import files

import yaml

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dm.agent import run_agent  # noqa: E402
from dm.eval.grading import (  # noqa: E402
    compute_facts,
    grade_contains,
    grade_numeric,
    grade_refusal,
    grade_set,
    parse_judge_verdict,
)
from dm.eval.schema import EvalCaseError, validate_cases  # noqa: E402
from dm.warehouse.store import append_log, connect_ro  # noqa: E402

_MAX_LOG_ANSWER = 1_200


def _truth(sql: str):
    con = connect_ro()
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _agent_result(value: object) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        raise EvalCaseError("agent result must be a mapping")
    answer = value.get("answer")
    session_id = value.get("session_id")
    if not isinstance(answer, str) or not answer:
        raise EvalCaseError("agent result answer must be a non-empty string")
    if not isinstance(session_id, str) or not session_id or len(session_id) > 256:
        raise EvalCaseError("agent result session_id must be a bounded non-empty string")
    return answer, session_id


def grade_llm_judge(question: str, expected: str, answer: str, facts: str = "") -> tuple[bool, str]:
    ref = expected + (f"\n实时核算事实（来自仓库，权威）：{facts}" if facts else "")
    prompt = (
        "你在给数据问答系统的回答打分，只看主要结论是否与『参考标准』一致。\n"
        f"问题：{question}\n参考标准：{ref}\n系统回答：{answer}\n"
        "若主要结论与参考标准一致，只回 PASS；否则只回 FAIL。"
    )
    from dm.llm import chat

    try:
        output = chat([{"role": "user", "content": prompt}], temperature=0.0, timeout=120)
    except RuntimeError:
        return False, "JUDGE_UNAVAILABLE"
    return parse_judge_verdict(output)


def _grade(case: Mapping[str, object], answer: str) -> tuple[bool, str]:
    grader = str(case["grader"])
    if grader == "numeric":
        return grade_numeric(_truth(str(case["truth_sql"])), answer)
    if grader == "set":
        return grade_set(_truth(str(case["truth_sql"])), answer)
    if grader == "refusal":
        ok, expected = grade_refusal(answer)
        return ok, str(case.get("expected", expected))
    if grader == "contains":
        return grade_contains(case["expected_contains"], answer)
    if grader == "llm_judge":
        facts = compute_facts(case.get("truth_facts"), _truth)
        ok, verdict = grade_llm_judge(
            str(case["question"]), str(case.get("expected", "")), answer, facts
        )
        expected = str(case.get("expected", ""))
        if facts:
            expected += f"  [核算:{facts}]"
        return ok, expected + f"  [判:{verdict}]"
    raise EvalCaseError(f"unsupported grader after validation: {grader}")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def main() -> None:
    raw_cases = yaml.safe_load((files("dm.eval") / "eval_set.yaml").read_text(encoding="utf-8"))
    cases = validate_cases(raw_cases)
    now = _utc_now()
    run_id = "R" + now.strftime("%Y%m%dT%H%M%S%fZ")
    print(f"=== Eval 跑批 {run_id}，共 {len(cases)} 例（每例会真实调用智能体）===\n")

    passed = 0
    for case in cases:
        result = run_agent(
            str(case["question"]),
            channel="eval",
            role=str(case.get("role", "管理员")),
            purpose=str(case.get("purpose", "财务对账")),
        )
        answer, session_id = _agent_result(result)
        ok, expected = _grade(case, answer)
        passed += int(ok)
        append_log(
            "eval_run",
            {
                "run_id": run_id,
                "case_id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "expected": expected,
                "got": answer[:_MAX_LOG_ANSWER],
                "grader": case["grader"],
                "passed": bool(ok),
                "session_id": session_id,
                "ts": _utc_now().isoformat(timespec="seconds"),
            },
        )
        mark = "✅PASS" if ok else "❌FAIL"
        print(f'  [{mark}] {case["id"]!s:>3} {case["category"]!s:12}/{case["grader"]!s:9} 期望≈{expected[:34]}')

    rate = passed / len(cases) * 100
    print(f"\n=== 通过 {passed}/{len(cases)}  ({rate:.0f}%)  run_id={run_id} ===")


if __name__ == "__main__":
    main()

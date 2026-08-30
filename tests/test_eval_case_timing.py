from dm.eval.run_eval import _execute_case


CASE = {"id": "C1", "category": "direct", "question": "q", "grader": "refusal"}


def test_case_execution_records_monotonic_duration():
    ticks = iter([10.0, 10.125])

    def clock():
        return next(ticks)

    outcome = _execute_case(
        CASE,
        agent_runner=lambda *a, **k: {"answer": "暂无数据", "session_id": "S1"},
        grader=lambda case, answer: (True, "expected"),
        clock=clock,
    )
    assert outcome.duration_ms == 125


def test_case_execution_clamps_backward_clock_anomalies():
    ticks = iter([10.0, 9.0])
    outcome = _execute_case(
        CASE,
        agent_runner=lambda *a, **k: {"answer": "暂无数据", "session_id": "S1"},
        grader=lambda case, answer: (True, "expected"),
        clock=lambda: next(ticks),
    )
    assert outcome.duration_ms == 0

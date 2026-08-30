from dm.eval.run_eval import CaseOutcome, _execute_case


CASE = {"id": "C1", "category": "direct", "question": "q", "grader": "refusal"}


def test_case_execution_contains_agent_failures_without_leaking_details():
    def broken_agent(*args, **kwargs):
        raise RuntimeError("token=secret")

    outcome = _execute_case(CASE, agent_runner=broken_agent)
    assert outcome == CaseOutcome(False, "agent unavailable", "", "", "AGENT_ERROR")
    assert "secret" not in repr(outcome)


def test_case_execution_contains_invalid_agent_envelopes():
    outcome = _execute_case(CASE, agent_runner=lambda *a, **k: {"answer": "ok"})
    assert outcome.error_code == "AGENT_RESULT_ERROR"


def test_case_execution_contains_grader_failures_but_keeps_answer_context():
    def agent(*args, **kwargs):
        return {"answer": "safe answer", "session_id": "S1"}

    def grader(case, answer):
        raise RuntimeError("postgres://secret")

    outcome = _execute_case(CASE, agent_runner=agent, grader=grader)
    assert outcome.error_code == "GRADER_ERROR"
    assert outcome.answer == "safe answer"
    assert outcome.session_id == "S1"

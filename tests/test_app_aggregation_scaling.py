from dm.app.data import agg_eval, agg_sessions


class IterationCountingList(list):
    def __init__(self, values):
        super().__init__(values)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()


def test_session_aggregation_groups_input_in_one_pass():
    steps = IterationCountingList([
        {"session_id": "s2", "step_no": 2, "channel": "web", "final_answer": "done"},
        {"session_id": "s1", "step_no": 1, "channel": "cli", "question": "first"},
        {"session_id": "s2", "step_no": 1, "channel": "web", "question": "second"},
        {"session_id": "", "step_no": 1, "question": "orphan"},
    ])

    result = agg_sessions(steps)

    assert steps.iterations == 1
    assert result["order"] == ["s2", "s1"]
    assert result["n_sessions"] == 2
    assert result["recent"][0]["sid"] == "s1"
    assert result["recent"][1] == {
        "sid": "s2", "question": "second", "answer": "done",
        "channel": "web", "ts": "", "steps": 2,
    }


def test_eval_aggregation_groups_input_in_one_pass():
    runs = IterationCountingList([
        {"run_id": "r1", "category": "sql", "passed": True, "ts": "2026-10-18"},
        {"run_id": "r2", "category": "policy", "passed": False, "ts": "2026-10-18"},
        {"run_id": "r1", "category": "sql", "passed": False, "ts": "2026-10-18"},
        {"run_id": None, "category": "ignored", "passed": True},
    ])

    result = agg_eval(runs)

    assert runs.iterations == 1
    assert result["order"] == ["r1", "r2"]
    assert result["trend"] == [
        {"run_id": "r1", "total": 2, "passed": 1, "rate": 50, "ts": "2026-10-18"},
        {"run_id": "r2", "total": 1, "passed": 0, "rate": 0, "ts": "2026-10-18"},
    ]
    assert result["latest_rows"] == [runs[1]]

from dm.llm import _close_response


class _BrokenCloseResponse:
    def close(self):
        raise RuntimeError("adapter cleanup failed")


class _NoCloseResponse:
    pass


def test_response_cleanup_is_best_effort():
    _close_response(_BrokenCloseResponse())
    _close_response(_NoCloseResponse())

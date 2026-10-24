import io
import threading

from dm.agent import core


class _ObservedStream(io.StringIO):
    def __init__(self, value: str):
        super().__init__(value)
        self.reader_threads: list[int] = []

    def read(self, size: int = -1) -> str:
        self.reader_threads.append(threading.get_ident())
        return super().read(size)


def test_stderr_drain_runs_in_background_and_retains_only_its_budget(monkeypatch):
    payload = "backend detail\n" * 100
    stream = _ObservedStream(payload)
    monkeypatch.setattr(core, "_SUBPROCESS_STDERR_LIMIT", 37)
    caller_thread = threading.get_ident()

    thread, state = core._start_bounded_stderr_drain(stream)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert state["text"] == payload[:37]
    assert stream.tell() == len(payload)
    assert stream.reader_threads
    assert all(reader != caller_thread for reader in stream.reader_threads)


def test_bounded_stream_keeps_draining_after_the_retained_prefix():
    payload = "x" * (core._SUBPROCESS_READ_CHUNK * 3)
    stream = io.StringIO(payload)

    assert core._drain_bounded_stream(stream, limit=5) == "xxxxx"
    assert stream.tell() == len(payload)

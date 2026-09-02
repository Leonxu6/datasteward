import pytest

from scripts import audit_runtime_global_state as audit


def test_faulthandler_mutations_are_reported():
    source = """
import faulthandler
faulthandler.enable()
faulthandler.register(12)
faulthandler.unregister(12)
faulthandler.disable()
"""
    findings = audit.findings_for_source(source, path="worker.py")
    assert len(findings) == 4
    assert all(item.startswith("worker.py:") for item in findings)
    assert any("faulthandler.enable" in item for item in findings)
    assert any("faulthandler.register" in item for item in findings)
    assert any("faulthandler.unregister" in item for item in findings)
    assert any("faulthandler.disable" in item for item in findings)


def test_tracemalloc_lifecycle_mutations_are_reported():
    source = """
import tracemalloc
tracemalloc.start(25)
tracemalloc.clear_traces()
tracemalloc.stop()
"""
    findings = audit.findings_for_source(source, path="memory.py")
    assert len(findings) == 3
    assert any("tracemalloc.start" in item for item in findings)
    assert any("tracemalloc.clear_traces" in item for item in findings)
    assert any("tracemalloc.stop" in item for item in findings)


def test_process_priority_mutations_are_reported():
    source = """
import os
os.nice(5)
os.setpriority(os.PRIO_PROCESS, 0, 10)
"""
    findings = audit.findings_for_source(source, path="scheduler.py")
    assert len(findings) == 2
    assert any("os.nice" in item for item in findings)
    assert any("os.setpriority" in item for item in findings)


def test_process_fork_hook_registration_is_reported():
    findings = audit.findings_for_source(
        "import os\nos.register_at_fork(after_in_child=lambda: None)\n",
        path="worker.py",
    )
    assert len(findings) == 1
    assert "os.register_at_fork" in findings[0]


def test_signal_routing_mutations_are_reported():
    source = """
import signal
signal.set_wakeup_fd(3)
signal.siginterrupt(signal.SIGINT, False)
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
"""
    findings = audit.findings_for_source(source, path="signals.py")
    assert len(findings) == 3
    assert any("signal.set_wakeup_fd" in item for item in findings)
    assert any("signal.siginterrupt" in item for item in findings)
    assert any("signal.pthread_sigmask" in item for item in findings)


def test_local_object_calls_are_ignored():
    assert audit.findings_for_source("buffer.append(1)\n") == []


def test_source_and_path_contracts_are_explicit():
    with pytest.raises(ValueError, match="source"):
        audit.findings_for_source(None)  # type: ignore[arg-type]
    for path in ("", " worker.py", "worker.py "):
        with pytest.raises(ValueError, match="path"):
            audit.findings_for_source("pass\n", path=path)

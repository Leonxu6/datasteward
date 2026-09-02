# Runtime boundary audits

DataSteward's maintenance suite treats long-running service processes as shared infrastructure. Code that silently blocks forever, replaces the process, launches interactive children, or deserializes executable objects can destabilize unrelated workers even when the local call looks small.

The runtime-global-state advisory composes focused checks for four families:

- **Unbounded waits:** `concurrent.futures.wait`, `as_completed`, `asyncio.wait`, and `select.select` should declare finite timeout behavior where supported.
- **Process and user-visible side effects:** direct `os.fork`, `os.forkpty`, `os.exec*`, `os.spawn*`, `pty.spawn`, `signal.pause`, and `webbrowser.open*` calls are surfaced for explicit lifecycle review.
- **Executable or implementation-specific deserialization:** `marshal`, pandas pickle, dill, cloudpickle, NumPy pickle-enabled loads, and `torch.load(..., weights_only=False)` create deliberate trust boundaries.
- **Native/runtime hooks:** dynamic `ctypes` library loads, SQLite extension loading, `runpy` execution, and `subprocess.Popen(preexec_fn=...)` execute code outside ordinary Python call boundaries.

These checks remain **advisory** rather than blocking. Reviewers should require a clear answer for trust source, lifetime or timeout, cancellation behavior, and cleanup before accepting a new finding.

Each rule has a focused regression test so detection can improve without turning the suite into a broad text grep.

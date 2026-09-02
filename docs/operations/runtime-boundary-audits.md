# Runtime boundary audits

DataSteward's maintenance suite treats long-running service processes as shared infrastructure. Code that silently blocks forever, replaces the process, launches interactive children, or deserializes executable objects can destabilize unrelated workers even when the local call looks small.

The runtime-global-state advisory now composes dedicated checks for four families:

- **Unbounded waits:** `concurrent.futures.wait`, `as_completed`, `asyncio.wait`, and `select.select` must declare finite timeout behavior where the API supports it.
- **Process and user-visible side effects:** direct `os.fork`, `os.forkpty`, `os.exec*`, `os.spawn*`, `pty.spawn`, `signal.pause`, and `webbrowser.open*` calls are surfaced for explicit lifecycle review.
- **Executable or implementation-specific deserialization:** `marshal`, pandas pickle, dill, cloudpickle, NumPy pickle-enabled loads, and `torch.load(..., weights_only=False)` are visible before they become hidden trust boundaries.
- **Native/runtime hooks:** dynamic `ctypes` library loads, SQLite extension loading, `runpy` execution, and `subprocess.Popen(preexec_fn=...)` are flagged because they execute code outside ordinary Python call boundaries.

These checks are **advisory** rather than blocking. Existing integrations can be legitimate, but every new occurrence should answer three questions during review: what is the trust boundary, what bounds the lifetime or wait, and how does failure remain isolated from the host process?

Each rule has a focused regression test so future refactors can improve detection without turning the maintenance suite into a broad text grep.
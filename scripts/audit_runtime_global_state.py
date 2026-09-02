"""Detect process-wide runtime mutations in DataSteward production modules.

This audit is advisory because global-state and process-boundary APIs can be legitimate integration choices. Findings make those choices visible before one component silently alters or blocks unrelated workers.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from scripts.audit_ast_rules import call_name, iter_calls
from scripts.audit_common import print_failures, production_python_files, require_root
from scripts.audit_as_completed_timeout import audit_source as audit_as_completed_timeout
from scripts.audit_asyncio_wait_timeout import audit_source as audit_asyncio_wait_timeout
from scripts.audit_cloudpickle_load import audit_source as audit_cloudpickle_load
from scripts.audit_concurrent_wait_timeout import audit_source as audit_concurrent_wait_timeout
from scripts.audit_dill_load import audit_source as audit_dill_load
from scripts.audit_marshal_load import audit_source as audit_marshal_load
from scripts.audit_native_library_load import audit_source as audit_native_library_load
from scripts.audit_numpy_pickle_load import audit_source as audit_numpy_pickle_load
from scripts.audit_os_exec import audit_source as audit_os_exec
from scripts.audit_os_fork import audit_source as audit_os_fork
from scripts.audit_os_forkpty import audit_source as audit_os_forkpty
from scripts.audit_os_spawn import audit_source as audit_os_spawn
from scripts.audit_pandas_pickle_load import audit_source as audit_pandas_pickle_load
from scripts.audit_pty_spawn import audit_source as audit_pty_spawn
from scripts.audit_runpy_execution import audit_source as audit_runpy_execution
from scripts.audit_select_timeout import audit_source as audit_select_timeout
from scripts.audit_signal_pause import audit_source as audit_signal_pause
from scripts.audit_sqlite_load_extension import audit_source as audit_sqlite_load_extension
from scripts.audit_subprocess_preexec_fn import audit_source as audit_subprocess_preexec_fn
from scripts.audit_torch_pickle_load import audit_source as audit_torch_pickle_load
from scripts.audit_webbrowser_open import audit_source as audit_webbrowser_open

_RULE_MESSAGES={
"faulthandler.enable":"faulthandler configuration is process-wide","faulthandler.disable":"faulthandler configuration is process-wide","faulthandler.register":"faulthandler signal registration is process-wide","faulthandler.unregister":"faulthandler signal registration is process-wide","tracemalloc.start":"tracemalloc lifecycle is process-wide","tracemalloc.stop":"tracemalloc lifecycle is process-wide","tracemalloc.clear_traces":"tracemalloc traces are process-wide","os.nice":"process priority changes affect the entire service process","os.setpriority":"process priority changes affect scheduler behavior","os.register_at_fork":"fork hooks persist for the process lifetime","signal.set_wakeup_fd":"signal wakeup routing is process-wide","signal.siginterrupt":"signal syscall restart behavior is process-wide","signal.pthread_sigmask":"signal masks affect thread/process delivery semantics","threading.settrace":"default tracing affects subsequently created threads","threading.setprofile":"default profiling affects subsequently created threads","logging.disable":"logging.disable changes process-wide logging visibility","warnings.resetwarnings":"resetwarnings replaces process-wide warning filters","warnings.filterwarnings":"warning filters are process-wide ambient state","warnings.simplefilter":"warning filters are process-wide ambient state","numpy.seterrcall":"NumPy error callbacks are ambient numerical state","numpy.setbufsize":"NumPy ufunc buffer size is ambient numerical state","np.seterrcall":"NumPy error callbacks are ambient numerical state","np.setbufsize":"NumPy ufunc buffer size is ambient numerical state","sys.setswitchinterval":"thread scheduling interval is interpreter-wide state","sys.setdlopenflags":"dynamic-loader flags alter subsequent extension imports","gc.freeze":"garbage-collector freeze state affects the entire interpreter","gc.unfreeze":"garbage-collector freeze state affects the entire interpreter"}
_EXTRA_SOURCE_AUDITS=(audit_concurrent_wait_timeout,audit_as_completed_timeout,audit_asyncio_wait_timeout,audit_select_timeout,audit_signal_pause,audit_os_fork,audit_os_forkpty,audit_os_exec,audit_os_spawn,audit_pty_spawn,audit_webbrowser_open,audit_native_library_load,audit_runpy_execution,audit_marshal_load,audit_numpy_pickle_load,audit_pandas_pickle_load,audit_torch_pickle_load,audit_dill_load,audit_cloudpickle_load,audit_sqlite_load_extension,audit_subprocess_preexec_fn)

def findings_for_source(source: str, *, path: str="<memory>") -> list[str]:
    if not isinstance(source,str): raise ValueError("source must be text")
    if not isinstance(path,str) or not path or path!=path.strip(): raise ValueError("path must be clean non-empty text")
    findings=[]
    for c in iter_calls(source):
        name=call_name(c); detail=_RULE_MESSAGES.get(name or "")
        if detail: findings.append(f"{path}:{c.lineno}: {name}: {detail}")
    for rule in _EXTRA_SOURCE_AUDITS: findings.extend(f"{path}: {item}" for item in rule(source))
    return findings

def audit(root: Path) -> list[str]:
    root=require_root(root); findings=[]
    for rel in production_python_files(root):
        path=root/rel
        if path.is_symlink(): continue
        try: source=path.read_text(encoding="utf-8")
        except (OSError,UnicodeError) as exc:
            findings.append(f"{rel}: unreadable source ({exc.__class__.__name__})"); continue
        findings.extend(findings_for_source(source,path=rel.as_posix()))
    return findings

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("root",nargs="?",default=".")
    return print_failures(audit(Path(p.parse_args(argv).root)))
if __name__=="__main__": raise SystemExit(main())

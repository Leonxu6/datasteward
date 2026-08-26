from scripts.audit_subprocess_shell import audit_source

def test_shell_audit_accepts_argument_lists():assert audit_source('subprocess.run(["echo","ok"])\n')==[]
def test_shell_audit_reports_shell_true():assert audit_source('subprocess.run("echo ok",shell=True)\n')==["subprocess shell=True on line 1"]

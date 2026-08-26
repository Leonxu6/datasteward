from scripts.audit_dynamic_code import audit_source

def test_dynamic_code_audit_accepts_regular_calls():assert audit_source("value=int(raw)\n")==[]
def test_dynamic_code_audit_reports_eval_exec():assert audit_source("eval(raw)\nexec(code)\n")==["dynamic code execution via eval() on line 1","dynamic code execution via exec() on line 2"]

from scripts.audit_markdown_fences import audit_text

def test_markdown_fences_accept_balanced():assert audit_text("```python\nprint('ok')\n```\n")==[]
def test_markdown_fences_report_unclosed():assert audit_text("intro\n```python\nprint('oops')\n")==['unclosed Markdown fence opened on line 2']

from scripts.audit_decimal_default_context import audit_source


def test_decimal_default_context_audit_allows_local_contexts():
    assert audit_source("ctx = decimal.Context(prec=28)\n") == []


def test_decimal_default_context_audit_reports_global_default_mutation():
    assert audit_source("decimal.DefaultContext.prec = 12\n") == ["decimal.DefaultContext mutation changes process Decimal defaults on line 1"]

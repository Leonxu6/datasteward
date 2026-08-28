from scripts.audit_json_nan import audit_source


def test_json_nan_audit_allows_strict_json():
    assert audit_source("json.dumps(data, allow_nan=False)\n") == []


def test_json_nan_audit_reports_default_nan_behavior():
    assert audit_source("json.dumps(data)\n") == [
        "json.dumps() may emit NaN/Infinity on line 1; set allow_nan=False for interoperable JSON"
    ]

from scripts.audit_path_text_encoding import audit_source


def test_path_text_encoding_accepts_explicit_encoding():
    assert audit_source("Path('x').read_text(encoding='utf-8')\n") == []


def test_path_text_encoding_reports_default_encoding():
    assert audit_source("Path('x').write_text(data)\n") == [
        "Path.write_text without explicit encoding on line 1"
    ]

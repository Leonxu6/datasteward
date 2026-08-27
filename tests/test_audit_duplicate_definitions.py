from scripts.audit_duplicate_definitions import audit_source


def test_duplicate_definition_audit_allows_unique_names():
    assert audit_source("def one():\n    pass\n\nclass Box:\n    def two(self):\n        pass\n") == []


def test_duplicate_definition_audit_reports_shadowed_definitions():
    source = "def one():\n    pass\ndef one():\n    pass\nclass Box:\n    def two(self):\n        pass\n    def two(self):\n        pass\n"
    assert audit_source(source) == [
        "duplicate definition one on line 3",
        "duplicate definition Box.two on line 8",
    ]

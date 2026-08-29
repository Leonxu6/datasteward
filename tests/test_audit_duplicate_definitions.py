from scripts.audit_duplicate_definitions import audit_source


def test_duplicate_definition_audit_allows_unique_names():
    assert audit_source("def one():\n    pass\n\nclass Box:\n    def two(self):\n        pass\n") == []


def test_duplicate_definition_audit_reports_shadowed_definitions():
    source = "def one():\n    pass\ndef one():\n    pass\nclass Box:\n    def two(self):\n        pass\n    def two(self):\n        pass\n"
    assert audit_source(source) == [
        "duplicate definition one on line 3",
        "duplicate definition Box.two on line 8",
    ]


def test_duplicate_definition_audit_allows_property_setters_and_deleters():
    source = """class Connection:
    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._autocommit = value

    @autocommit.deleter
    def autocommit(self):
        del self._autocommit
"""
    assert audit_source(source) == []

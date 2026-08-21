import unittest

from dm.kg.cypher_guard import validate_readonly_cypher


class CypherGuardTests(unittest.TestCase):
    def assert_allowed(self, cypher: str):
        clean, error, masked = validate_readonly_cypher(cypher)
        self.assertIsNone(error, msg=error)
        self.assertTrue(clean)
        self.assertTrue(masked)

    def assert_rejected(self, cypher, fragment: str):
        _, error, _ = validate_readonly_cypher(cypher)
        self.assertIsNotNone(error)
        self.assertIn(fragment, error)

    def test_allows_read_queries_and_one_trailing_semicolon(self):
        for cypher in (
            "MATCH (n) RETURN n",
            "OPTIONAL MATCH (n) RETURN n;",
            "RETURN 1 AS ok",
            "WITH 1 AS x RETURN x",
            "UNWIND [1,2] AS x RETURN x",
        ):
            with self.subTest(cypher=cypher):
                self.assert_allowed(cypher)

    def test_ignores_keywords_and_semicolons_inside_literals_comments_and_identifiers(self):
        self.assert_allowed("MATCH (n) WHERE n.note = 'delete; call' RETURN n")
        self.assert_allowed("// delete; call\nMATCH (n) RETURN n")
        self.assert_allowed("MATCH (`delete`) RETURN `delete` /* call; */")

    def test_rejects_writes_procedures_and_multiple_statements(self):
        for cypher, fragment in (
            ("MATCH (n) DELETE n", "not allowed"),
            ("CALL db.labels()", "must start"),
            ("MATCH (n) CALL db.labels() RETURN n", "not allowed"),
            ("RETURN 1; RETURN 2", "one Cypher"),
        ):
            with self.subTest(cypher=cypher):
                self.assert_rejected(cypher, fragment)

    def test_rejects_unclosed_quotes_and_comments(self):
        for cypher in ("RETURN 'oops", "MATCH (`oops) RETURN 1", "RETURN 1 /* oops"):
            with self.subTest(cypher=cypher):
                self.assert_rejected(cypher, "unclosed")

    def test_rejects_empty_and_non_string_queries(self):
        for cypher in (None, 1, "", "   "):
            with self.subTest(cypher=cypher):
                self.assert_rejected(cypher, "query")


if __name__ == "__main__":
    unittest.main()

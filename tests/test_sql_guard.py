import unittest
from unittest.mock import patch

from dm.tools.sql_guard import tables_in, validate_readonly


class ReadonlySqlGuardTests(unittest.TestCase):
    def assert_allowed(self, sql: str):
        clean, error = validate_readonly(sql)
        self.assertIsNone(error, msg=error)
        self.assertTrue(clean)

    def assert_rejected(self, sql, fragment: str):
        _, error = validate_readonly(sql)
        self.assertIsNotNone(error)
        self.assertIn(fragment, error)

    def test_allows_forbidden_words_inside_string_literals(self):
        self.assert_allowed("SELECT 'delete; drop table users' AS note")

    def test_allows_forbidden_words_inside_comments(self):
        self.assert_allowed("-- delete old rows\nSELECT 1 /* drop table users; */")

    def test_allows_quoted_identifiers_that_match_keywords(self):
        self.assert_allowed('SELECT "delete" FROM "show"')

    def test_rejects_actual_multiple_statements(self):
        self.assert_rejected("SELECT 1; SELECT 2", "单条")

    def test_rejects_actual_write_keywords(self):
        self.assert_rejected("WITH changed AS (DELETE FROM orders RETURNING *) SELECT * FROM changed", "写/DDL")

    def test_rejects_repeated_statement_terminators(self):
        self.assert_rejected("SELECT 1;;", "单条")

    def test_rejects_unterminated_literals_and_comments(self):
        for sql in ("SELECT 'oops", 'SELECT "oops', "SELECT 1 /* oops"):
            with self.subTest(sql=sql):
                self.assert_rejected(sql, "未闭合")

    def test_rejects_empty_or_non_string_sql(self):
        for sql in (None, 1, "", "   "):
            with self.subTest(sql=sql):
                self.assert_rejected(sql, "SQL")

    @patch("dm.tools.sql_guard.business_table_names", return_value=["orders", "customers"])
    def test_tables_in_ignores_names_in_literals_and_comments(self, _business_names):
        sql = "SELECT * FROM orders WHERE note = 'customers' -- customers\n"
        self.assertEqual(tables_in(sql), ["orders"])

    @patch("dm.tools.sql_guard.business_table_names", return_value=["orders"])
    def test_tables_in_handles_non_string_input(self, _business_names):
        self.assertEqual(tables_in(None), [])


if __name__ == "__main__":
    unittest.main()

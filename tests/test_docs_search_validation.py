import unittest
from unittest.mock import patch

from dm.docs.search import _normalize_query, _normalize_top_k, search


class SearchValidationTests(unittest.TestCase):
    def test_normalizes_surrounding_query_whitespace(self):
        self.assertEqual(_normalize_query("  supplier S001  "), "supplier S001")

    def test_rejects_empty_or_non_string_queries(self):
        for value in (None, 1, "", "   "):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _normalize_query(value)

    def test_accepts_integer_result_limits(self):
        for value in (1, 5, 100):
            with self.subTest(value=value):
                self.assertEqual(_normalize_top_k(value), value)

    def test_rejects_boolean_float_and_out_of_range_limits(self):
        for value in (True, False, 1.0, "5", 0, -1, 101):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _normalize_top_k(value)

    @patch("dm.docs.search.embed_one")
    def test_validation_happens_before_embedding(self, embed_one):
        for query, top_k in (("", 5), ("valid", 0)):
            with self.subTest(query=query, top_k=top_k):
                with self.assertRaises(ValueError):
                    search(query, top_k=top_k)
        embed_one.assert_not_called()


if __name__ == "__main__":
    unittest.main()

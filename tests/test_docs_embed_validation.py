import os
import unittest
from unittest.mock import patch

from dm.docs import embed


class EmbedValidationTests(unittest.TestCase):
    def test_backend_accepts_supported_values_case_insensitively(self):
        for value, expected in (("hash", "hash"), (" HASH ", "hash"), ("FASTEMBED", "fastembed")):
            with self.subTest(value=value), patch.dict(os.environ, {"DM_EMBED_BACKEND": value}):
                self.assertEqual(embed._embedding_backend(), expected)

    def test_backend_rejects_unknown_or_empty_values(self):
        for value in ("", "torch", "fast-embed", "none"):
            with self.subTest(value=value), patch.dict(os.environ, {"DM_EMBED_BACKEND": value}):
                with self.assertRaisesRegex(ValueError, "fastembed or hash"):
                    embed._embedding_backend()

    @patch("dm.docs.embed._fastembed_model")
    def test_unknown_backend_fails_before_loading_model(self, model):
        with patch.dict(os.environ, {"DM_EMBED_BACKEND": "typo"}):
            with self.assertRaises(ValueError):
                embed.embed(["hello"])
        model.assert_not_called()

    def test_normalize_texts_accepts_strings_generators_and_empty_batches(self):
        self.assertEqual(embed._normalize_texts("hello"), ["hello"])
        self.assertEqual(embed._normalize_texts(item for item in ("a", "b")), ["a", "b"])
        self.assertEqual(embed._normalize_texts([]), [])

    def test_normalize_texts_rejects_non_string_items_and_non_iterables(self):
        for value in (None, 7, b"bytes", ["ok", 7], [None]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    embed._normalize_texts(value)

    @patch("dm.docs.embed._fastembed_model")
    def test_empty_batch_returns_without_loading_model(self, model):
        self.assertEqual(embed.embed([]), [])
        model.assert_not_called()

    def test_hash_backend_accepts_empty_text_as_deterministic_zero_vector(self):
        with patch.dict(os.environ, {"DM_EMBED_BACKEND": "hash"}):
            vector = embed.embed_one("")
        self.assertEqual(len(vector), embed.DIM)
        self.assertTrue(all(value == 0.0 for value in vector))

    def test_embedding_dimension_accepts_ascii_positive_range(self):
        for value, expected in (("1", 1), ("512", 512), ("16384", 16384)):
            with self.subTest(value=value):
                self.assertEqual(embed._embedding_dimension(value), expected)

    def test_embedding_dimension_rejects_invalid_or_ambiguous_values(self):
        for value in ("", "0", "-1", "16385", "512.0", "５１２", " 512 ", None):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "DM_EMBED_DIM"):
                    embed._embedding_dimension(value)


if __name__ == "__main__":
    unittest.main()

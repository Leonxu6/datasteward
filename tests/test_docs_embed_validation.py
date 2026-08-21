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


if __name__ == "__main__":
    unittest.main()

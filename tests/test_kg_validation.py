import unittest

from dm.kg.validation import bounded_int, label_name, required_text


class KgValidationTests(unittest.TestCase):
    def test_bounded_int_accepts_values_inside_range(self):
        self.assertEqual(bounded_int(1, name="limit", minimum=1, maximum=10), 1)
        self.assertEqual(bounded_int(10, name="limit", minimum=1, maximum=10), 10)

    def test_bounded_int_rejects_bool_float_string_and_out_of_range_values(self):
        for value in (True, False, 1.0, "2", 0, 11):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    bounded_int(value, name="limit", minimum=1, maximum=10)

    def test_required_text_rejects_padding_controls_and_non_strings(self):
        for value in (None, 7, "", " padded", "padded ", "line\nfeed"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    required_text(value, name="entity_id")

    def test_required_text_enforces_length(self):
        with self.assertRaisesRegex(ValueError, "at most 4"):
            required_text("abcde", name="id", max_length=4)

    def test_label_name_accepts_safe_ascii_identifiers(self):
        for value in ("Customer", "SalesOrder", "Material_2"):
            with self.subTest(value=value):
                self.assertEqual(label_name(value), value)

    def test_label_name_rejects_sanitization_ambiguous_inputs(self):
        for value in ("Customer-Type", "Customer Type", "客户", "1Customer", "Customer)"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    label_name(value)


if __name__ == "__main__":
    unittest.main()

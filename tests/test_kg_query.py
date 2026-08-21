import unittest
from unittest.mock import patch

from dm.kg.query import find_related, impact_path


class KgQueryTests(unittest.TestCase):
    @patch("dm.kg.query.run_read", return_value=[{"id": "B"}])
    def test_find_related_uses_validated_bounds_and_parameterized_entity(self, run_read):
        result = find_related("M0001", max_hops=3, limit=12)

        self.assertEqual(result["entity"], "M0001")
        self.assertEqual(result["max_hops"], 3)
        self.assertEqual(result["count"], 1)
        cypher = run_read.call_args.args[0]
        self.assertIn("[*1..3]", cypher)
        self.assertIn("LIMIT 12", cypher)
        self.assertEqual(run_read.call_args.kwargs, {"id": "M0001"})

    @patch("dm.kg.query.run_read")
    def test_find_related_rejects_invalid_inputs_before_database_access(self, run_read):
        cases = (
            ("", 2, 30),
            (" M0001", 2, 30),
            ("M0001", True, 30),
            ("M0001", 0, 30),
            ("M0001", 5, 30),
            ("M0001", 2, 0),
            ("M0001", 2, 101),
        )
        for entity_id, hops, limit in cases:
            with self.subTest(entity_id=entity_id, hops=hops, limit=limit):
                with self.assertRaises(ValueError):
                    find_related(entity_id, max_hops=hops, limit=limit)
        run_read.assert_not_called()

    @patch("dm.kg.query.run_read", return_value=[{"id": "SO001"}])
    def test_impact_path_interpolates_only_validated_label_and_bounds(self, run_read):
        result = impact_path("M0001", "SalesOrder", max_hops=5, limit=7)

        self.assertEqual(result["target_type"], "SalesOrder")
        self.assertEqual(result["count"], 1)
        cypher = run_read.call_args.args[0]
        self.assertIn("[*1..5]", cypher)
        self.assertIn("(b:SalesOrder)", cypher)
        self.assertIn("LIMIT 7", cypher)
        self.assertEqual(run_read.call_args.kwargs, {"id": "M0001"})

    @patch("dm.kg.query.run_read")
    def test_impact_path_rejects_unsafe_labels_and_limits_before_database_access(self, run_read):
        cases = (
            ("M0001", "Customer-Type", 4, 20),
            ("M0001", "Customer) MATCH (x", 4, 20),
            ("M0001", "Customer", True, 20),
            ("M0001", "Customer", 7, 20),
            ("M0001", "Customer", 4, 51),
            (" M0001", "Customer", 4, 20),
        )
        for entity_id, target_type, hops, limit in cases:
            with self.subTest(target_type=target_type, hops=hops, limit=limit):
                with self.assertRaises(ValueError):
                    impact_path(entity_id, target_type, max_hops=hops, limit=limit)
        run_read.assert_not_called()


if __name__ == "__main__":
    unittest.main()

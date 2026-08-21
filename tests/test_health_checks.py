import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from dm.health.checks import _to_dt, run_check


class HealthCheckTests(unittest.TestCase):
    def _freshness_check(self):
        return {
            "id": "freshness_test",
            "type": "freshness",
            "table": "inventory",
            "column": "update_time",
            "max_age_days": 30,
            "severity": "warn",
            "desc": "freshness",
        }

    def test_to_dt_preserves_datetime_instances(self):
        value = datetime(2026, 8, 21, 9, 0, tzinfo=timezone.utc)
        self.assertIs(_to_dt(value), value)

    def test_to_dt_parses_iso_text_and_bytes(self):
        self.assertEqual(_to_dt("2026-08-21T09:00:00"), datetime(2026, 8, 21, 9, 0))
        parsed = _to_dt(b"2026-08-21T17:00:00+08:00")
        self.assertEqual(parsed.utcoffset().total_seconds(), 8 * 3600)

    def test_to_dt_rejects_malformed_empty_and_unsupported_values(self):
        for value in ("not-a-date", "", "   ", None, 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _to_dt(value)

    @patch("dm.health.checks._sr_scalar", return_value="definitely-not-a-date")
    def test_freshness_check_fails_instead_of_treating_bad_timestamp_as_fresh(self, _scalar):
        result = run_check(self._freshness_check())

        self.assertEqual(result["status"], "fail")
        self.assertIn("invalid timestamp", result["message"])

    def test_freshness_check_warns_when_source_clock_is_in_the_future(self):
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        with patch("dm.health.checks._sr_scalar", return_value=future):
            result = run_check(self._freshness_check())

        self.assertEqual(result["status"], "warn")
        self.assertIn("超前", result["message"])
        self.assertIn("未来", result["actual"])


if __name__ == "__main__":
    unittest.main()

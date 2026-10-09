import unittest
from core.geo_time import (
    get_system_timezone_info,
    get_location_info,
    get_realtime_prompt_context,
)


class TestGeoTime(unittest.TestCase):
    def test_system_timezone(self):
        tz_info = get_system_timezone_info()
        self.assertIn("timezone_name", tz_info)
        self.assertIn("timezone_identifier", tz_info)
        self.assertIn("utc_offset", tz_info)
        self.assertTrue(tz_info["utc_offset"].startswith("UTC+") or tz_info["utc_offset"].startswith("UTC-"))

    def test_location_info_no_fake_gps(self):
        loc = get_location_info()
        self.assertIn("city", loc)
        self.assertIn("country", loc)
        self.assertIn("source", loc)
        self.assertIn("is_exact_gps", loc)
        # Must never claim fake GPS precision
        self.assertFalse(loc["is_exact_gps"])

    def test_prompt_context_contains_time_and_date(self):
        ctx = get_realtime_prompt_context()
        self.assertIn("[REAL-TIME DATE, TIME & LOCATION]", ctx)
        self.assertIn("Timezone:", ctx)
        self.assertIn("Current Location:", ctx)
        self.assertIn("Do NOT", ctx)


if __name__ == "__main__":
    unittest.main()

import unittest
import tempfile
from pathlib import Path
from core.api_guard import (
    APIGuard,
    get_guard,
    is_kill_switch_active,
    set_kill_switch,
    redact_secrets,
    SlidingWindowRateLimiter,
    AgentLoopGuard,
    QuotaTracker,
)


class TestApiGuard(unittest.TestCase):
    def setUp(self):
        set_kill_switch(False)

    def tearDown(self):
        set_kill_switch(False)

    def test_secret_redaction(self):
        raw_key = "AIzaSyD_TEST_SECRET_KEY_1234567890123"
        text = f"Failed with API key {raw_key} on host"
        redacted = redact_secrets(text)
        self.assertNotIn(raw_key, redacted)
        self.assertIn("…", redacted)

        bearer_text = "Authorization: Bearer sk-1234567890abcdef123456"
        redacted_bearer = redact_secrets(bearer_text)
        self.assertNotIn("sk-1234567890abcdef123456", redacted_bearer)
        self.assertIn("***REDACTED***", redacted_bearer)

    def test_emergency_kill_switch(self):
        self.assertFalse(is_kill_switch_active())
        set_kill_switch(True)
        self.assertTrue(is_kill_switch_active())

        guard = get_guard()
        with self.assertRaises(RuntimeError):
            guard.assert_api_allowed("Gemini REST")

        set_kill_switch(False)
        self.assertFalse(is_kill_switch_active())

    def test_rate_limiter_window(self):
        limiter = SlidingWindowRateLimiter(max_requests=3, window_sec=60.0)
        self.assertTrue(limiter.acquire(block=False))
        self.assertTrue(limiter.acquire(block=False))
        self.assertTrue(limiter.acquire(block=False))
        # 4th request must be rejected in non-blocking mode
        self.assertFalse(limiter.acquire(block=False))

    def test_agent_loop_guard_identical(self):
        guard = AgentLoopGuard(max_identical=3, history_len=10)
        ok1, _ = guard.record_and_check("web_search", {"q": "news"})
        self.assertTrue(ok1)
        ok2, _ = guard.record_and_check("web_search", {"q": "news"})
        self.assertTrue(ok2)
        # 3rd identical should trip circuit breaker
        ok3, reason = guard.record_and_check("web_search", {"q": "news"})
        self.assertFalse(ok3)
        self.assertIn("Circuit breaker", reason)

    def test_agent_loop_guard_cyclic(self):
        guard = AgentLoopGuard(max_identical=5, history_len=20)
        for _ in range(2):
            guard.record_and_check("action_a", {})
            guard.record_and_check("action_b", {})
        guard.record_and_check("action_a", {})
        # 6th action in alternating cycle triggers loop breaker
        ok, reason = guard.record_and_check("action_b", {})
        self.assertFalse(ok)
        self.assertIn("alternating loop", reason)

    def test_quota_tracker_and_stats(self):
        tracker_file = Path(__file__).parent / "scratch_test_usage.json"
        try:
            if tracker_file.exists():
                tracker_file.unlink()
            tracker = QuotaTracker(tracker_file)
            tracker.record_usage(requests_count=5, tokens_count=1000)
            stats = tracker.get_stats()
            self.assertEqual(stats["daily_requests"], 5)
            self.assertEqual(stats["daily_tokens"], 1000)

            ok, _ = tracker.check_quota(daily_req_limit=10, daily_tok_limit=2000, monthly_req_limit=100)
            self.assertTrue(ok)

            ok_exceeded, reason = tracker.check_quota(daily_req_limit=4, daily_tok_limit=2000, monthly_req_limit=100)
            self.assertFalse(ok_exceeded)
            self.assertIn("Daily request quota exceeded", reason)
        finally:
            if tracker_file.exists():
                try:
                    tracker_file.unlink()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()

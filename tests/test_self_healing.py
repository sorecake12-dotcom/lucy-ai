import unittest
from core.self_healing_control import (
    SelfHealingController,
    FailureCategory,
    HealingResult,
    WindowManager,
)


class TestSelfHealingControl(unittest.TestCase):
    def test_diagnosis_backend_failsafe(self):
        err = Exception("PyAutoGUI failSafeException triggered at corner")
        cat = SelfHealingController.diagnose_failure(err)
        self.assertEqual(cat, FailureCategory.FAILED_INPUT_BACKEND)

    def test_diagnosis_permission_denied(self):
        err = PermissionError("Access is denied writing to foreground window buffer")
        cat = SelfHealingController.diagnose_failure(err)
        self.assertEqual(cat, FailureCategory.PERMISSION_PROBLEM)

    def test_diagnosis_timeout(self):
        err = TimeoutError("Timed out waiting for application response")
        cat = SelfHealingController.diagnose_failure(err)
        self.assertEqual(cat, FailureCategory.TEMP_PROCESS_FAILURE)

    def test_execute_with_healing_success(self):
        calls = []

        def successful_action():
            calls.append(1)
            return "typed ok"

        success, val, msg = SelfHealingController.execute_with_healing(
            action_name="test_type",
            action_fn=successful_action,
        )
        self.assertTrue(success)
        self.assertEqual(val, "typed ok")
        self.assertEqual(len(calls), 1)

    def test_execute_with_healing_recovery(self):
        attempts = 0

        def flaky_action():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise Exception("Timed out waiting for application window")
            return "typed after retry"

        success, val, msg = SelfHealingController.execute_with_healing(
            action_name="test_flaky",
            action_fn=flaky_action,
            max_retries=3,
        )
        self.assertTrue(success)
        self.assertEqual(val, "typed after retry")
        self.assertEqual(attempts, 2)

    def test_execute_with_healing_exhaustion(self):
        def permanent_fail():
            raise Exception("Timed out waiting for process")

        success, val, msg = SelfHealingController.execute_with_healing(
            action_name="permanent_fail",
            action_fn=permanent_fail,
            max_retries=2,
        )
        self.assertFalse(success)
        self.assertIn("failed after 2 self-healing attempts", msg)

    def test_window_manager_list(self):
        windows = WindowManager.list_windows()
        self.assertIsInstance(windows, list)


if __name__ == "__main__":
    unittest.main()

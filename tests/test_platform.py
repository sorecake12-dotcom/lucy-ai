"""
tests/test_platform.py — Test platform abstraction layer and compatibility.
"""

import unittest
from pathlib import Path

from core.platform_adapter import (
    get_desktop_dir,
    get_os_name,
    get_platform_capabilities,
    is_linux,
    is_mac,
    is_windows,
)


class TestPlatformAdapter(unittest.TestCase):
    def test_os_detection(self):
        name = get_os_name()
        self.assertIn(name, ("windows", "mac", "linux"))
        if is_windows():
            self.assertEqual(name, "windows")
            self.assertFalse(is_mac())
            self.assertFalse(is_linux())
        elif is_mac():
            self.assertEqual(name, "mac")
            self.assertFalse(is_windows())
            self.assertFalse(is_linux())
        elif is_linux():
            self.assertEqual(name, "linux")
            self.assertFalse(is_windows())
            self.assertFalse(is_mac())

    def test_desktop_dir(self):
        desk = get_desktop_dir()
        self.assertIsInstance(desk, Path)
        self.assertTrue(len(str(desk)) > 0)

    def test_capabilities(self):
        caps = get_platform_capabilities()
        self.assertTrue(caps["ai_chat"])
        self.assertTrue(caps["particle_visualizer"])
        self.assertTrue(caps["memory_manager"])
        self.assertTrue(caps["browser_automation"])


if __name__ == "__main__":
    unittest.main()

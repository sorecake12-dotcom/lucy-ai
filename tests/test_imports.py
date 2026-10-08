"""
tests/test_imports.py — Verify critical module imports across platforms.
"""

import sys
import unittest


class TestModuleImports(unittest.TestCase):
    def test_core_modules(self):
        import core.personality
        import core.animated_shapes
        import core.particle_blob
        import core.audio_devices
        import core.platform_adapter
        import core.action_loader
        import core.plugin_loader
        import core.undo

        self.assertEqual(core.personality.DEFAULT_PERSONALITY, "GF")
        self.assertIn("star", core.animated_shapes.available_shapes())
        self.assertIn("flower", core.animated_shapes.available_shapes())
        self.assertIn("human", core.animated_shapes.available_shapes())

    def test_memory_and_config(self):
        import memory.config_manager
        import memory.memory_manager

        self.assertEqual(memory.config_manager.get_assistant_name(), "LUCY")

    def test_actions_modules(self):
        import actions.particle_visualizer
        import actions.open_app
        import actions.computer_settings
        import actions.desktop
        import actions.reminder
        import actions.file_controller
        import actions.system_monitor

        self.assertIn("star", actions.particle_visualizer._DEFAULT_PALETTES)
        self.assertIn("flower", actions.particle_visualizer._DEFAULT_PALETTES)
        self.assertIn("human", actions.particle_visualizer._DEFAULT_PALETTES)


if __name__ == "__main__":
    unittest.main()

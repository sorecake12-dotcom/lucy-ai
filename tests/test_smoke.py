"""
tests/test_smoke.py — Headless smoke test for LUCY core engine.
"""

import unittest
from pathlib import Path

from core.action_loader import discover_actions
from core.personality import (
    MODE_ASSISTANT,
    MODE_GF,
    MODE_JARVIS,
    get_personality_prompt,
)


class TestSmokeEngine(unittest.TestCase):
    def test_personality_prompts(self):
        for mode in (MODE_GF, MODE_JARVIS, MODE_ASSISTANT):
            prompt = get_personality_prompt(mode)
            self.assertTrue(len(prompt) > 50)
            self.assertIn(mode, prompt)

    def test_action_loader(self):
        actions_dir = Path(__file__).resolve().parent.parent / "actions"
        registry = discover_actions(actions_dir)
        self.assertTrue(len(registry._actions) > 0)
        self.assertIn("particle_visualizer", registry._actions)
        decls = registry.get_tool_declarations()
        self.assertTrue(any(d["name"] == "particle_visualizer" for d in decls))


if __name__ == "__main__":
    unittest.main()

"""
tests/test_shapes.py — Test 3D procedural particle shape point clouds.
"""

import math
import unittest

from core.animated_shapes import SHAPE_BUILDERS, available_shapes, build


class TestAnimatedShapes(unittest.TestCase):
    def test_all_shapes_build(self):
        shapes = available_shapes()
        expected_shapes = [
            "car", "sports car", "television", "laptop", "fan", "chair", "table",
            "bird", "animal", "cat", "cube", "earth", "flower", "heart", "house",
            "human", "human head", "detailed face", "planet", "robot", "rocket",
            "saturn", "sphere", "star", "tree"
        ]
        for s in expected_shapes:
            self.assertIn(s, shapes, f"Missing shape in registry: {s}")

        for s in shapes:
            pts, grp = build(s, 500)
            self.assertGreaterEqual(len(pts), 250, f"Shape {s} produced too few points")
            self.assertEqual(len(pts), len(grp), f"Point and group mismatch for {s}")
            # Verify valid non-empty groups
            self.assertTrue(any(g >= 0 for g in grp), f"No valid group in {s}")
            # Ensure points normalized within roughly [-1.5, 1.5]
            for x, y, z in pts:
                dist = math.sqrt(x * x + y * y + z * z)
                self.assertLess(dist, 1.8, f"Point outside normalized boundary in {s}")


if __name__ == "__main__":
    unittest.main()

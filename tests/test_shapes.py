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
            "car", "cat", "cube", "earth", "flower", "heart", "house",
            "human", "planet", "robot", "rocket", "saturn", "sphere", "star", "tree"
        ]
        for s in expected_shapes:
            self.assertIn(s, shapes, f"Missing shape in registry: {s}")

        for s in shapes:
            pts, grp = build(s, 400)
            self.assertGreaterEqual(len(pts), 200, f"Shape {s} produced too few points")
            self.assertEqual(len(pts), len(grp), f"Point and group mismatch for {s}")
            # Ensure points normalized within roughly [-1.2, 1.2]
            for x, y, z in pts:
                dist = math.sqrt(x * x + y * y + z * z)
                self.assertLess(dist, 2.0, f"Point outside normalized boundary in {s}")


if __name__ == "__main__":
    unittest.main()

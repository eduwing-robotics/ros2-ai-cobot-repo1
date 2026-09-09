import unittest
import math
import numpy as np
from audit_vrm_rotation_evidence import angles, axis_delta


class RotationTests(unittest.TestCase):
    def test_axis_wrap(self):
        self.assertAlmostEqual(axis_delta(-90), 0)
        self.assertAlmostEqual(axis_delta(89, -89), -2)
        self.assertAlmostEqual(axis_delta(270), 0)

    def test_rectangle_rotation(self):
        for deg in [-15, 0, 15]:
            rad = math.radians(deg)
            r = np.array([[math.cos(rad), -math.sin(rad)], [math.sin(rad), math.cos(rad)]])
            poly = np.array([[-5,-10],[5,-10],[5,10],[-5,10]]) @ r.T + 50
            result = angles(dict(polygon=poly.tolist(), long_axis_deg=90+deg))
            for value in result:
                self.assertAlmostEqual(value, deg, places=4)

    def test_missing_and_square_are_ambiguous(self):
        self.assertIsNone(angles(None))
        self.assertIsNone(angles(dict(polygon=[[0,0],[10,0],[10,10],[0,10]], long_axis_deg=0)))

    def test_translation_does_not_change_angle(self):
        poly = np.array([[0,0],[10,0],[10,20],[0,20]])
        a = angles(dict(polygon=poly.tolist(), long_axis_deg=90))
        b = angles(dict(polygon=(poly+200).tolist(), long_axis_deg=90))
        np.testing.assert_allclose(a, b, atol=1e-6)


if __name__ == '__main__':
    unittest.main()

import unittest
from audit_vrm_normal_envelope import excess


class EnvelopeTests(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(excess([1,2,11,12], [[0,0,10,10],[2,4,12,14]]),[0]*4)

    def test_each_side(self):
        self.assertEqual(excess([-1,6,15,8], [[0,0,10,10],[2,4,12,14]]),[1,2,3,2])

    def test_invalid_reference(self):
        with self.assertRaises(ValueError):
            excess([0]*4, [[0]*4])


if __name__ == '__main__':
    unittest.main()

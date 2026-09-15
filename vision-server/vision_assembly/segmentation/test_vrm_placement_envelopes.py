import unittest
from replay_vrm_placement_envelopes import compare


class EnvelopeTests(unittest.TestCase):
    def test_uncertainty_abstains_without_pass(self):
        refs = [[0, 1, 2], [2, 3, 4]]
        self.assertEqual(compare([3, 2, 5], refs, [2, 2, 2]), 'UNKNOWN')
        self.assertEqual(compare([5, 2, 7], refs, [2, 2, 2]), 'RIGHT_SHIFT_CANDIDATE')
        self.assertEqual(compare([4, 2, 6], refs, [2, 2, 2]), 'UNKNOWN')

    def test_nonfinite_rejected(self):
        self.assertEqual(compare([float('inf'), 2, 5], [[0, 1, 2]]), 'UNKNOWN')
        self.assertEqual(compare([3, 2, 5], [[0, 1, 2]], [-1, 0, 0]), 'UNKNOWN')

    def test_missing_is_unknown(self):
        self.assertEqual(compare(None, [[1, 2, 3]]), 'UNKNOWN')
        self.assertEqual(compare([1, 2, 3], [None]), 'UNKNOWN')

    def test_inside_is_not_pass(self):
        self.assertEqual(compare([1, 2, 3], [[0, 1, 2], [2, 3, 4]]), 'WITHIN_OBSERVED_LEFT_ENVELOPE')

    def test_right_requires_both_center_and_edge(self):
        refs = [[0, 1, 2], [2, 3, 4]]
        self.assertEqual(compare([3, 2, 5], refs), 'RIGHT_SHIFT_CANDIDATE')
        self.assertEqual(compare([3, 2, 3], refs), 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()

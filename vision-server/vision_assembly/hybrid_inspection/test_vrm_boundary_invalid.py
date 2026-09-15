"""Isolated fail-safe input tests; no main integration or model loading."""
import copy
import unittest

import numpy as np

from vrm_boundary_advisory import evaluate


class InvalidBoundaryTests(unittest.TestCase):
    def arguments(self):
        return [dict(position=[10, 0, 20], axes=[20, 20]),
                [[0, 0, 10], [1, 0, 11]], [[0, 0], [1, 1]],
                [2, 0, 2], [2, 2]]

    def assert_abstains(self, args):
        result = evaluate(*args)
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['authority'], 'ADVISORY_ONLY')
        self.assertEqual(result['codes'], [])
        self.assertNotIn('right_excess_px', result)

    def test_malformed_samples(self):
        for sample in (None, {}, [], 1, 'sample', np.array(1), {'position': [10, 0, 20]},
                       {'axes': [20, 20]}):
            with self.subTest(sample=sample):
                args = self.arguments()
                args[0] = sample
                self.assert_abstains(args)

    def test_malformed_vectors(self):
        for field, length in (('position', 3), ('axes', 2)):
            for value in ([], 1, {}, 'bad', [1] * (length - 1),
                          [1] * (length + 1), [[1] * length],
                          ['1'] * length, [True] * length, [1j] * length):
                with self.subTest(field=field, value=value):
                    args = self.arguments()
                    args[0][field] = value
                    self.assert_abstains(args)

    def test_malformed_references_and_margins(self):
        for index in range(1, 5):
            for value in (None, [], 1, {}, 'bad', [1], [[1]],
                          [[0, 0, 0], [0]], [True, True], ['1', '2']):
                with self.subTest(index=index, value=value):
                    args = self.arguments()
                    args[index] = value
                    self.assert_abstains(args)

    def test_every_numeric_coordinate_must_be_finite(self):
        for bad in (float('nan'), float('inf'), -float('inf'), None, '0', True, 1j):
            for field, size in (('position', 3), ('axes', 2)):
                for coordinate in range(size):
                    with self.subTest(bad=bad, field=field, coordinate=coordinate):
                        args = self.arguments()
                        # Object dtype prevents mixed booleans/strings being silently coerced.
                        if isinstance(bad, (bool, str, complex)):
                            args[0][field] = np.array(args[0][field], dtype=object)
                        args[0][field][coordinate] = bad
                        self.assert_abstains(args)
            for index, width in ((1, 3), (2, 2), (3, 3), (4, 2)):
                for coordinate in range(width):
                    with self.subTest(bad=bad, index=index, coordinate=coordinate):
                        args = self.arguments()
                        if isinstance(bad, (bool, str, complex)):
                            args[index] = np.array(args[index], dtype=object)
                        target = args[index][0] if index < 3 else args[index]
                        target[coordinate] = bad
                        self.assert_abstains(args)

    def test_negative_margins(self):
        for index, width in ((3, 3), (4, 2)):
            for coordinate in range(width):
                args = self.arguments()
                args[index][coordinate] = -1
                self.assert_abstains(args)

    def test_mixed_boolean_numeric_lists(self):
        args = self.arguments()
        args[0]['position'][1] = True
        self.assert_abstains(args)
        args = self.arguments()
        args[1][0][1] = False
        self.assert_abstains(args)
        args = self.arguments()
        args[3][1] = False
        self.assert_abstains(args)

    def test_finite_values_that_overflow_arithmetic(self):
        args = self.arguments()
        args[0]['position'][0] = 1.7e308
        args[1] = [[-1.7e308, 0, 0]]
        self.assert_abstains(args)
        args = self.arguments()
        args[0]['axes'] = [1.7e308, 1.7e308]
        args[2] = [[-1.7e308, -1.7e308]]
        self.assert_abstains(args)

    def test_invalid_angles_cannot_leave_partial_right_code(self):
        args = self.arguments()
        args[0]['axes'] = [20, float('nan')]
        self.assert_abstains(args)

    def test_valid_candidates_and_input_preservation(self):
        args = self.arguments()
        before = copy.deepcopy(args)
        result = evaluate(*args)
        self.assertEqual(result['codes'], ['RIGHT?', 'ROT?'])
        self.assertEqual(result['right_excess_px'], [7, 7])
        self.assertEqual(args, before)
        self.assertIs(result['measured'], args[0])
        args[0]['axes'] = None
        self.assertEqual(evaluate(*args)['codes'], ['RIGHT?'])
        args[2] = []
        self.assert_abstains(args)

    def test_valid_guard_and_modulo_thresholds(self):
        for excess, expected in ((0.5, []), (1, []), (1.0001, ['RIGHT?'])):
            args = self.arguments()
            args[0] = dict(position=[3 + excess, 0, 13 + excess], axes=[0, 0])
            self.assertEqual(evaluate(*args)['codes'], expected)
        for angle, expected in ((3, []), (3.0001, ['ROT?']), (180, [])):
            args = self.arguments()
            args[0] = dict(position=[0, 0, 10], axes=[angle, angle])
            self.assertEqual(evaluate(*args)['codes'], expected)


if __name__ == '__main__':
    unittest.main()

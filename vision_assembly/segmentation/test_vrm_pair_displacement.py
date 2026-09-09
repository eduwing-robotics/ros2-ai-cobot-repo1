import unittest
from compare_vrm_pair_displacement import displacement


def row(bounds):
    return dict(samples=[dict(unique_count=1, primary=dict(extent_in_fixed_crop=list(bounds))) for _ in range(5)])


class DisplacementTests(unittest.TestCase):
    def test_translation_is_preserved_not_recentered(self):
        result = displacement(row([10,20,30,40]), row([10,35,30,62]))
        self.assertEqual(result['delta_lower_px'], [0,15,0,22])
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertFalse(result['confirmed_defect'])

    def test_unavailable_is_not_missing(self):
        current = row([10,20,30,40])
        current['samples'][0].update(unique_count=0, primary=None)
        self.assertNotIn('delta_lower_px', displacement(row([10,20,30,40]), current))

    def test_unchanged_is_not_pass(self):
        result = displacement(row([10,20,30,40]), row([10,20,30,40]))
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['delta_upper_px'], [0]*4)


if __name__ == '__main__':
    unittest.main()

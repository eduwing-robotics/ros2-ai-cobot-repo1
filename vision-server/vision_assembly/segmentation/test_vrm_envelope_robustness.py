import unittest
from validate_vrm_envelope_robustness import reference
from replay_vrm_placement_envelopes import compare, features


def row(x):
    return dict(crop_origin_px=[3, 10], primary=dict(
        center_px=[x, 50], polygon=[[x-5, 40], [x+5, 40], [x+5, 60], [x-5, 60]]))


class RobustnessTests(unittest.TestCase):
    def setUp(self):
        self.frames = {t: {f'vrm_{i:02d}': row(x) for i in range(1, 6)}
                       for t, x in [('a', 50), ('b', 51), ('excluded', 100)]}

    def test_excluded_scene_cannot_inflate_margin(self):
        refs, margin = reference(self.frames, ['a', 'b'])
        self.assertEqual(margin, [1, 0, 1])
        self.assertEqual(max(v[0] for v in refs['vrm_01']), 54)

    def test_all_parts_shift_is_not_subtracted(self):
        refs, margin = reference(self.frames, ['a', 'b'])
        for slot, value in self.frames['excluded'].items():
            self.assertEqual(compare(features(value), refs[slot], margin), 'RIGHT_SHIFT_CANDIDATE')

    def test_missing_reference_fails_closed(self):
        self.frames['a']['vrm_01']['primary'] = None
        with self.assertRaises(ValueError):
            reference(self.frames, ['a', 'b'])

    def test_duplicate_reference_rejected(self):
        with self.assertRaises(ValueError):
            reference(self.frames, ['a', 'a'])


if __name__ == '__main__':
    unittest.main()

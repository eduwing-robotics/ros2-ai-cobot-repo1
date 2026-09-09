import unittest
import numpy as np
from vrm_boundary_advisory import evaluate, measure, VrmBoundaryAdvisory


class BoundaryTests(unittest.TestCase):
    def test_display_groups_without_mutating_raw_codes(self):
        from main import display_codes
        raw = ['RIGHT?', 'POSE?', 'SEATING?', 'ROT?', 'DIR?', 'PINS?']
        self.assertEqual(display_codes(raw), ['POSITION?', 'DIRECTION?', 'PINS?'])
        self.assertEqual(len(raw), 6)

    def test_render_summary(self):
        from main import _render_evidence_report
        image = np.zeros((1266,1600,3), np.uint8)
        result = _render_evidence_report(image, image, image, [], [], 'UNKNOWN', .98,
                                         {'vrm_01': {'codes': ['RIGHT?']}, 'vrm_02': {'codes': []}})
        self.assertEqual(result.shape[0], 990)
        self.assertGreater(np.count_nonzero(result[-50:]), 0)

    def test_fusion_cannot_promote_boundary_vote(self):
        from main import fuse_required_stages
        status, _ = fuse_required_stages({'vrm_boundary': {'status': 'UNKNOWN', 'authority': 'ADVISORY_ONLY'}})
        self.assertEqual(status, 'UNKNOWN')

    def test_missing_is_unknown(self):
        self.assertEqual(evaluate(None, [], [], [], [])['status'], 'UNKNOWN')

    def test_candidates_never_authoritative(self):
        r = evaluate(dict(position=[10, 0, 20], axes=[20, 20]),
                     [[0,0,10],[1,0,11]], [[0,0],[1,1]], [2,0,2], [2,2])
        self.assertEqual(r['codes'], ['RIGHT?', 'ROT?'])
        self.assertEqual(r['status'], 'UNKNOWN')
        self.assertEqual(r['authority'], 'ADVISORY_ONLY')

    def test_inside_is_not_pass(self):
        r = evaluate(dict(position=[0,0,10], axes=[0,0]), [[0,0,10]], [[0,0]], [2,0,2], [2,2])
        self.assertEqual(r['codes'], [])
        self.assertEqual(r['status'], 'UNKNOWN')

    def test_single_pixel_excess_abstains(self):
        r = evaluate(dict(position=[3.5,0,14],axes=[0,0]),
                     [[0,0,10],[1,0,11]], [[0,0]], [2,0,2], [2,2])
        self.assertEqual(r['codes'], [])
        self.assertEqual(r['status'], 'UNKNOWN')
        self.assertEqual(r['right_excess_px'], [.5,1])

    def test_vertical_axis(self):
        r = measure([[0,0],[10,0],[10,20],[0,20]], [3,10])
        self.assertAlmostEqual(r['axes'][0], 0)
        self.assertAlmostEqual(r['axes'][1], 0)
        self.assertEqual(r['position'], [8,20,13])

    def test_invalid_outline(self):
        self.assertIsNone(measure([[0,0],[1,1]], [0,0]))


if __name__ == '__main__':
    unittest.main()

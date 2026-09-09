"""Synthetic/offline release-audit tests; never import the model provider."""
import copy
import json
import unittest

from audit_geometry_release import ROOT, SOURCES, boundary_probe, summarize, render


class GeometryReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / SOURCES['boundary']).read_text()
        cls.probe = boundary_probe(cls.source)
        cls.data = {key: json.loads((ROOT / path).read_text())
                    for key, path in SOURCES.items() if key != 'boundary'}

    def test_wrap_fix_preserves_uncertainty(self):
        self.assertFalse(self.probe['reproduced'])
        self.assertEqual(self.probe['actual_codes'], [])
        self.assertEqual(self.probe['actual_status'], 'UNKNOWN')
        self.assertEqual(self.probe['actual_authority'], 'ADVISORY_ONLY')
        self.assertLess(self.probe['axial_distance_deg'], self.probe['margin_deg'][0])

    def test_units_never_converted_or_promoted(self):
        result = summarize(self.data, self.probe)
        self.assertIsNone(result['millimetres']['measured_clearance_mm'])
        self.assertFalse(result['pixels']['pixel_to_mm_conversion_performed'])
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertEqual(result['release_readiness'], 'BLOCKED')
        self.assertEqual(result['millimetres']['cad_nominal_vrm']['total_clearance_mm'], [1, 1])
        self.assertEqual(result['millimetres']['user_reported_dimensions']['total_clearance_xy_mm'], [1.5, 1])

    def test_saved_repeatability_recomputed(self):
        result = summarize(self.data, self.probe)
        self.assertTrue(result['pixels']['source_summary_matches'])
        self.assertEqual([r['range_px'] for r in result['pixels']['wall_repeatability_recomputed']], [2, 0, 0, 1, 0])

    def test_seating_label_not_overwritten_by_process_request(self):
        result = summarize(self.data, self.probe)
        rows = result['physical_seating_vs_process_position']
        reviewed = [r for r in rows if r['process_position_review']]
        self.assertEqual(len(reviewed), 1)
        row = reviewed[0]
        self.assertEqual(row['explicit_expected_pose_label'], 'PASS')
        self.assertEqual(row['physical_seating_label'], 'FLAT_AGAINST_RIGHT_WALL')
        self.assertEqual(row['process_position_review']['user_requested_disposition'], 'POSITION_ERROR')
        self.assertEqual(row['status'], 'UNKNOWN')

    def test_unmatched_or_duplicate_hash_does_not_invent_labels(self):
        for duplicate in (False, True):
            data = copy.deepcopy(self.data)
            if duplicate:
                data['labels']['scenes'] *= 2
            else:
                for row in data['position']['rows']:
                    row['input_sha256'] = 'unmatched'
            for row in summarize(data, self.probe)['physical_seating_vs_process_position']:
                self.assertIsNone(row['explicit_expected_pose_label'])
                self.assertIsNone(row['process_position_review'])

    def test_repeat_summary_mismatch_detected(self):
        data = copy.deepcopy(self.data)
        data['wall']['rows'][0]['right_groove_board_x_px'] += 10
        self.assertFalse(summarize(data, self.probe)['pixels']['source_summary_matches'])

    def test_sources_unmutated_and_report_bounded(self):
        before = copy.deepcopy(self.data)
        result = summarize(self.data, self.probe)
        self.assertEqual(self.data, before)
        self.assertLess(len(render(result).splitlines()), 50)
        for key in ('runtime_changed', 'training_labels_changed', 'robot_command_sent',
                    'conveyor_command_sent', 'capture_performed', 'gpu_used'):
            self.assertFalse(result[key])


if __name__ == '__main__':
    unittest.main()

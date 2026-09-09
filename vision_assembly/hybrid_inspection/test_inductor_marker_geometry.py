import unittest
import cv2
import numpy as np
from inductor_marker_geometry import measure_dark_mark


class MarkerTests(unittest.TestCase):
    def test_patchcore_baseline_is_advisory_display_only(self):
        from main import inductor_anomaly_visible
        good = dict(component_key='inductor',authority='ADVISORY_ONLY',score=.46,normal_p99=.309,fail_min=None)
        self.assertTrue(inductor_anomaly_visible(good))
        for changes in [dict(score=.2),dict(score=.330201149),dict(score=.309*1.20),dict(score=float('nan')),dict(normal_p99=None),
                        dict(authority='UNAVAILABLE'),dict(component_key='smd_capacitor')]:
            self.assertFalse(inductor_anomaly_visible({**good,**changes}))
        for score in [.423793, .463599, .5961, .7128, .9662]:
            self.assertTrue(inductor_anomaly_visible({**good, 'score': score}))

    def test_saved_normal_and_rotation_controls(self):
        from pathlib import Path
        from opencv_inspectors import check_inductor_marker
        root = Path(__file__).resolve().parents[2] / 'runtime/inspection/hybrid_fixed_slot'
        cases = [('20260906_182517_135335', 'PASS'),
                 ('20260906_175326_427204', 'FAIL'),
                 ('20260906_174102_525585', 'FAIL'),
                 ('20260906_172537_068340', 'FAIL')]
        paths = [root / name / 'fixed_slots/inductor/inductor_02.png' for name, _ in cases]
        if not all(p.exists() for p in paths):
            self.skipTest('Local captured regression fixtures not installed')
        for path, (_, expected) in zip(paths, cases):
            result = check_inductor_marker(cv2.imread(str(path)), expected_inner_edge_deg=85.6)
            self.assertEqual(result.status, expected, str(path))
            self.assertEqual(result.authority, 'ADVISORY_ONLY')
            self.assertLess(result.measured['white_top_radius_px'], 50)

    def image(self):
        image=np.full((150,150,3),30,np.uint8)
        cv2.circle(image,(75,75),55,(240,240,240),-1)
        return image

    def test_blank_is_unavailable(self):
        self.assertIsNone(measure_dark_mark(self.image(),[75,75],55))

    def test_mark_tilt_not_outer_circle(self):
        from opencv_inspectors import check_inductor_marker
        image=self.image()
        cv2.line(image,(48,50),(48,100),(15,15,15),7)
        normal=measure_dark_mark(image,[75,75],55)
        rotated=cv2.warpAffine(image,cv2.getRotationMatrix2D((75,75),20,1),(150,150))
        tilted=measure_dark_mark(rotated,[75,75],55)
        self.assertLess(normal['axis_error_deg'],2)
        self.assertGreater(tilted['axis_error_deg'],15)
        self.assertGreater(tilted['elongation'],3)
        self.assertEqual(check_inductor_marker(image).status, 'PASS')
        self.assertEqual(check_inductor_marker(rotated).status, 'FAIL')
        clockwise=cv2.warpAffine(image,cv2.getRotationMatrix2D((75,75),-20,1),(150,150))
        self.assertEqual(check_inductor_marker(clockwise, expected_inner_edge_deg=90).status, 'FAIL')


if __name__=='__main__':
    unittest.main()

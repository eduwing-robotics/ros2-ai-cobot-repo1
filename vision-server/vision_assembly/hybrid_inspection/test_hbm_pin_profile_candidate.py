"""Synthetic checks and optional strictly offline saved-crop diagnostic export.

Run: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
vision_assembly.hybrid_inspection.test_hbm_pin_profile_candidate
Export: python3 -m vision_assembly.hybrid_inspection.test_hbm_pin_profile_candidate
--artifacts (writes only the scoped hbm_pins artifact directory).
"""
import json
from pathlib import Path
import unittest

import cv2
import numpy as np

from vision_assembly.hybrid_inspection.hbm_pin_profile_candidate import inspect_hbm_pin_rows


STRIPS = {'left': (8, 8, 20, 112), 'right': (60, 8, 72, 112)}


def synthetic():
    rgb = np.full((120, 80, 3), 45, np.uint8)
    for x in (8, 60):
        for y in range(12, 105, 12):
            rgb[y:y+6, x:x+12] = 210
    return rgb


def inspect(rgb, **kw):
    args = dict(strips=STRIPS, reference_rgb=synthetic(), reference_reliable=True,
                orientation_usable=True, angle_error_deg=0, quality_usable=True)
    args.update(kw)
    return inspect_hbm_pin_rows(rgb, **args)


class HbmProfileTests(unittest.TestCase):
    def test_normal_and_missing(self):
        normal = synthetic()
        before = normal.copy()
        self.assertEqual(inspect(normal)['evidence']['diagnostic'], 'NO_LARGE_ROW_DEFICIT_OBSERVED')
        np.testing.assert_array_equal(normal, before)
        normal[36:42, 8:20] = 45
        out = inspect(normal)
        self.assertEqual(out['evidence']['diagnostic'], 'ROW_DEFICIT_CANDIDATE')
        self.assertTrue(out['evidence']['sides']['left']['deficit_intervals'])
        self.assertFalse(out['evidence']['sides']['right']['deficit_intervals'])
        self.assertEqual(out['status'], 'UNKNOWN')
        self.assertEqual(out['authority'], 'ADVISORY_ONLY')

    def test_collapsed_like_and_small_print(self):
        rgb = synthetic()
        rgb[36:42, 8:18] = 45
        self.assertEqual(inspect(rgb)['evidence']['diagnostic'], 'ROW_DEFICIT_CANDIDATE')
        rgb = synthetic()
        rgb[36, 8:20] = 45
        out = inspect(rgb)['evidence']
        self.assertEqual(out['diagnostic'], 'NO_LARGE_ROW_DEFICIT_OBSERVED')
        self.assertEqual(out['sides']['left']['white_profile'][28], 0)

    def test_missing_reference(self):
        for args in ({'reference_rgb': None}, {'reference_reliable': False},
                     {'reference_rgb': np.zeros((10, 10, 3), np.uint8)}):
            self.assertEqual(inspect(synthetic(), **args)['evidence']['diagnostic'], 'UNKNOWN')

    def test_glare_dark_blur(self):
        for value in (0, 180, 255):
            rgb = synthetic()
            rgb[8:112, 8:20] = value
            out = inspect(rgb)['evidence']
            self.assertEqual(out['diagnostic'], 'UNKNOWN')
            self.assertFalse(out['sides']['left']['deficit_intervals'])

    def test_orientation_and_quality(self):
        for args in ({'angle_error_deg': 90}, {'angle_error_deg': 180},
                     {'orientation_usable': False}, {'quality_usable': False},
                     {'orientation_usable': 'True'}):
            self.assertEqual(inspect(synthetic(), **args)['evidence']['diagnostic'], 'UNKNOWN')

    def test_finite_guards(self):
        for angle in (float('nan'), float('inf'), None, '0', True):
            result = inspect(synthetic(), angle_error_deg=angle)
            self.assertEqual(result['evidence']['diagnostic'], 'UNKNOWN')
            json.dumps(result, allow_nan=False)
        for rgb in (np.full((120, 80, 3), np.nan), synthetic().astype(float), None):
            self.assertEqual(inspect(rgb)['evidence']['diagnostic'], 'UNKNOWN')
        for strips in ({}, {'left': (-1, 8, 20, 112), 'right': STRIPS['right']},
                       {'left': (float('nan'), 8, 20, 112), 'right': STRIPS['right']},
                       {'left': STRIPS['left'], 'right': STRIPS['left']}):
            self.assertEqual(inspect(synthetic(), strips=strips)['evidence']['diagnostic'], 'UNKNOWN')

    def test_horizontal_and_unresolved_reference(self):
        rgb = synthetic().transpose(1, 0, 2).copy()
        strips = {s: (y0, x0, y1, x1) for s, (x0, y0, x1, y1) in STRIPS.items()}
        self.assertEqual(inspect(rgb, strips=strips, reference_rgb=rgb, axis='x')
                         ['evidence']['diagnostic'], 'NO_LARGE_ROW_DEFICIT_OBSERVED')
        self.assertEqual(inspect(synthetic(), reference_rgb=np.full_like(synthetic(), 45))
                         ['evidence']['diagnostic'], 'UNKNOWN')


def export_artifacts():
    root = Path(__file__).resolve().parents[2]
    target = root / 'runtime/inspection/parallel_completion_20260908/hbm_pins'
    target.mkdir(parents=True, exist_ok=True)
    cases = []
    for label in ('synthetic_normal', 'synthetic_missing'):
        rgb = synthetic()
        if label.endswith('missing'):
            rgb[36:42, 8:20] = 45
        cases.append((label, rgb, STRIPS, inspect(rgb), 'synthetic only'))
    # Fixed saved current-board runs; no discovery of cameras or model imports.
    for label, run in (
        ('saved_183239', 'normal_replay_183239/20260908_104846_044564'),
        ('saved_183151', 'normal_replay_183151/20260908_104821_534807'),
    ):
        folder = root / 'runtime/inspection/confirmed_controls_20260908' / run
        crops = sorted((folder / 'fixed_slots/hbm').glob('*.png'))
        if not crops:
            continue
        src = crops[0]
        bgr = cv2.imread(str(src))
        if bgr is None:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        # Exploratory strips, NOT calibrated body/pin geometry.
        strips = {'left': (int(w*.12), int(h*.18), int(w*.32), int(h*.82)),
                  'right': (int(w*.68), int(h*.18), int(w*.88), int(h*.82))}
        result = inspect_hbm_pin_rows(rgb, strips=strips, slot_id=src.stem)
        result['evidence']['source'] = str(src.relative_to(root))
        result['evidence']['limits'] = 'Exploratory strips; orientation, visibility and reference unverified; no real defect labels.'
        cases.append((label, rgb, strips, result, str(src)))
    for label, rgb, strips, result, source in cases:
        canvas = cv2.copyMakeBorder(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
                                    0, 100, 0, 0, cv2.BORDER_CONSTANT)
        for side, (x0, y0, x1, y1) in strips.items():
            color = (40, 210, 80) if side == 'left' else (240, 160, 40)
            cv2.rectangle(canvas, (x0, y0), (x1-1, y1-1), color, 1)
            profile = result['evidence']['sides'][side]['white_profile']
            points = np.array([(int(i*(rgb.shape[1]-1)/max(1, len(profile)-1)),
                                rgb.shape[0]+90-int(v*70)) for i, v in enumerate(profile)], np.int32)
            cv2.polylines(canvas, [points], False, color, 1)
        if not cv2.imwrite(str(target / (label+'.png')), canvas):
            raise RuntimeError('PNG export failed')
        (target / (label+'.json')).write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
        print(label, result['evidence']['diagnostic'], source)


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--artifacts']:
        export_artifacts()
    else:
        unittest.main()

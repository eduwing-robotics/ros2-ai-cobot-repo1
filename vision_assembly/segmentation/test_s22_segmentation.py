#!/usr/bin/env python3
"""Small offline checks for S22 segmentation labels and pose evidence."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from common import (
    CLASS_NAMES,
    NORMAL_CLASS_COUNTS,
    class_counts,
    load_yolo_segments,
    save_yolo_segments,
)
from predict_s22_parts_seg import (
    long_axis_angle_deg,
    match_candidates_to_slots,
    polygon_centroid,
)
from label_s22_parts_seg import mask_to_prompt_polygon, ordered_box


class S22SegmentationTest(unittest.TestCase):
    def test_normal_recipe_is_25_parts(self):
        self.assertEqual(sum(NORMAL_CLASS_COUNTS.values()), 25)
        self.assertEqual(set(NORMAL_CLASS_COUNTS), set(CLASS_NAMES))

    def test_yolo_polygon_round_trip(self):
        segments = [
            (0, np.asarray([[10, 20], [50, 20], [50, 70], [10, 70]], np.float32)),
            (5, np.asarray([[90, 90], [110, 88], [112, 105], [92, 108]], np.float32)),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.txt"
            save_yolo_segments(path, segments, 160, 126)
            loaded = load_yolo_segments(path, 160, 126)
        self.assertEqual(class_counts(loaded)["gpu"], 1)
        self.assertEqual(class_counts(loaded)["smd_capacitor"], 1)
        np.testing.assert_allclose(loaded[0][1], segments[0][1], atol=1e-4)

    def test_long_axis_is_undirected(self):
        horizontal = np.asarray([[0, 0], [40, 0], [40, 10], [0, 10]], np.float32)
        vertical = np.asarray([[0, 0], [10, 0], [10, 40], [0, 40]], np.float32)
        self.assertAlmostEqual(long_axis_angle_deg(horizontal), 0.0, places=3)
        self.assertAlmostEqual(long_axis_angle_deg(vertical), 90.0, places=3)

    def test_polygon_centroid_uses_area_not_vertex_density(self):
        l_shape = np.asarray(
            [[0, 0], [4, 0], [4, 1], [1, 1], [1, 4], [0, 4]], np.float32
        )
        np.testing.assert_allclose(polygon_centroid(l_shape), (9.5 / 7, 9.5 / 7), atol=1e-5)

    def test_slot_matching_uses_class_threshold_and_nearest_slot(self):
        slots = [
            {
                "slot_id": "power_module_01",
                "class_id": 2,
                "class_name": "power_module",
                "center": np.asarray((100, 100), np.float32),
                "size": np.asarray((50, 100), np.float32),
            }
        ]
        candidates = [
            {
                "class_id": 2,
                "confidence": 0.18,
                "center": np.asarray((104, 96), np.float32),
            }
        ]
        matched = match_candidates_to_slots(candidates, slots)
        self.assertIs(matched[0]["candidate"], candidates[0])

    def test_drag_box_is_ordered_and_rejects_clicks(self):
        self.assertEqual(ordered_box((80, 70), (20, 10), 100, 90), (20, 10, 80, 70))
        self.assertIsNone(ordered_box((10, 10), (14, 14), 100, 90))

    def test_prompt_mask_returns_component_polygon(self):
        mask = np.zeros((120, 160), np.uint8)
        mask[30:90, 50:110] = 1
        polygon = mask_to_prompt_polygon(mask, (45, 25, 115, 95))
        self.assertIsNotNone(polygon)
        self.assertGreaterEqual(len(polygon), 4)
        center = np.mean(polygon, axis=0)
        np.testing.assert_allclose(center, (79.5, 59.5), atol=2.0)


if __name__ == "__main__":
    unittest.main()

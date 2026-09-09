import sys
from pathlib import Path
import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_vrm_boundary_consensus import measure


def test_uniform_rectangle_boundaries():
    image = np.zeros((200, 160, 3), np.uint8)
    cv2.rectangle(image, (32,40), (128,160), (180,180,180), -1)
    saved = image.copy()
    for enhanced in (False, True):
        edges = measure(image, enhanced)
        assert all(abs(e['median_px']-v) <= 2 for e,v in zip(edges,(32,40,128,160)))
        assert all(e['spread_px'] <= 2 for e in edges)
    np.testing.assert_array_equal(image,saved)


def test_blank_has_no_edge_strength():
    # Agreement alone must not be interpreted as valid geometry.
    for edge in measure(np.zeros((200,160,3),np.uint8)):
        assert max(edge['strengths']) == 0

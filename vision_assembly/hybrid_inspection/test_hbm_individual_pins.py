import numpy as np
import cv2
from hbm_individual_pins import compare


def sample(missing=()):
    a = np.full((236, 169, 3), 25, np.uint8)
    for i, y in enumerate(range(35, 190, 18)):
        if i not in missing:
            cv2.circle(a, (132, y), 4, (220, 220, 220), -1)
    return a


def test_two_missing_end_pins():
    rows = compare(sample(), sample((7, 8)))
    assert rows[1]["missing_indices"] == [8, 9]
    assert len(rows[1]["defect_points_px"]) == 2


def test_normal_and_dark_abstain_from_defect():
    for image in (sample(), np.zeros_like(sample())):
        assert not any(s["missing_indices"] for s in compare(sample(), image))

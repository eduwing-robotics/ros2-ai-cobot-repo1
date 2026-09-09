import cv2
import numpy as np

from extract_inspection_roi import operator_source_corners


def _signed_area(points: np.ndarray) -> float:
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - y * np.roll(x, -1)))


def test_operator_roi_preserves_handedness_for_vertical_board():
    source_points = np.asarray(
        ((10.0, 20.0), (110.0, 20.0), (110.0, 220.0), (10.0, 220.0)),
        dtype=np.float32,
    )
    source = operator_source_corners(source_points)
    destination = np.asarray(
        ((0.0, 0.0), (199.0, 0.0), (199.0, 99.0), (0.0, 99.0)),
        dtype=np.float32,
    )

    assert _signed_area(source) * _signed_area(destination) > 0.0

    homography = cv2.getPerspectiveTransform(source, destination)
    linear_determinant = float(np.linalg.det(homography[:2, :2]))
    assert linear_determinant > 0.0

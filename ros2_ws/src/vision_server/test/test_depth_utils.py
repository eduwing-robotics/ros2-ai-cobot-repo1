import numpy as np

from vision_server.depth_utils import deproject_pixel, robust_box_depth


def test_robust_box_depth_ignores_zero_and_outlier():
    depth = np.full((20, 20), 500, dtype=np.uint16)
    depth[9:11, 9:11] = np.array([[0, 500], [500, 1500]], dtype=np.uint16)
    estimate = robust_box_depth(
        depth,
        (5, 5, 10, 10),
        scale_m_per_unit=0.001,
        roi_fraction=0.4,
        min_depth_m=0.05,
        max_depth_m=1.0,
    )
    assert estimate is not None
    u, v, z = estimate
    assert (u, v) == (10.0, 10.0)
    assert z == 0.5


def test_robust_box_depth_returns_none_without_valid_pixels():
    depth = np.zeros((10, 10), dtype=np.uint16)
    assert robust_box_depth(
        depth,
        (2, 2, 4, 4),
        scale_m_per_unit=0.001,
    ) is None


def test_deproject_pixel_uses_color_intrinsics():
    camera_matrix = np.array(
        [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]]
    )
    point = deproject_pixel(970.0, 520.0, 0.5, camera_matrix)
    assert point is not None
    assert np.isclose(point.x_m, 0.005)
    assert np.isclose(point.y_m, -0.010)
    assert np.isclose(point.z_m, 0.5)

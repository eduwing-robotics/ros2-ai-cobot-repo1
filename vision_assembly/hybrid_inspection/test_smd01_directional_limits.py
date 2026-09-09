import numpy as np
import pytest
from audit_smd01_directional_limits import envelope_audit


def test_signed_axes_and_leave_one_out():
    points = np.array([[0., 0.], [1., 1.], [2., 2.], [1., -1.], [1., 3.]])
    original = points.copy()
    result = envelope_audit(points, [True, True, True, False, False])
    assert result['defect_outside_by_axis'] == [[-1., 1.], [-1., 1.]]
    assert result['max_normal_expansion'] == [1., 1.]
    assert np.array_equal(points, original)


def test_inside_is_not_separated():
    result = envelope_audit([[0, 0], [1, 1], [2, 2], [1, 1]], [True, True, True, False])
    assert result['defect_outside_by_axis'] == [[-1., -1.]]


def test_insufficient_normals_rejected():
    with pytest.raises(ValueError):
        envelope_audit([[0, 0], [1, 1], [2, 2]], [True, True, False])

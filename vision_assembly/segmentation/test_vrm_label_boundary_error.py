import numpy as np
import pytest
from audit_vrm_label_boundary_error import errors


def test_identical_and_shifted():
    square=np.array([[10,10],[40,10],[40,40],[10,40]],dtype=float)
    same=errors(square,square,80,80)
    assert same['iou']==1 and same['boundary_max_px']==0
    shifted=errors(square,square+[3,0],80,80)
    assert shifted['extent_max_error_px']==3
    assert shifted['boundary_max_px']==pytest.approx(3)


def test_invalid_polygon():
    with pytest.raises(ValueError):
        errors([[0,0]],[[0,0]],10,10)

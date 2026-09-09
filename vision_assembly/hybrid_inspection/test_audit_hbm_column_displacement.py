import numpy as np
import pytest
from audit_hbm_column_displacement import displacement


def scene(dx=0):
    rgb=np.zeros((240,170,3),np.uint8)
    for x in (40,125):
        for y in range(30,160,18):
            rgb[y:y+4,x+dx:x+dx+3]=220
    return rgb


def test_displacement_not_compensated():
    a,b=scene(),scene(6)
    before=b.copy()
    result=displacement(a,b)
    assert np.array_equal(b,before)
    for side in result.values():
        assert side['dx_px']==pytest.approx(6)
        assert side['status']=='UNKNOWN'


def test_blank_abstains():
    assert all(v['dx_px'] is None for v in displacement(scene(),np.zeros_like(scene())).values())


def test_shape_mismatch():
    with pytest.raises(ValueError):
        displacement(scene(),scene()[:200])

import pytest
from vrm_access_geometry import nominal_gaps, access_evidence


def test_centered():
    assert nominal_gaps()==dict(left=.75,right=.75,top=.5,bottom=.5)


def test_left_offset():
    gaps=nominal_gaps(center_x_mm=-.25)
    assert gaps['right']==1 and gaps['left']==.5
    assert access_evidence(center_x_mm=-.25)['status']=='UNKNOWN'


def test_rotation_reduces_corner_gap():
    assert nominal_gaps(center_x_mm=-.25,angle_deg=3)['right']<1
    assert nominal_gaps(angle_deg=3)==nominal_gaps(angle_deg=-3)


def test_outside_and_invalid():
    assert nominal_gaps(center_x_mm=2)['right']<0
    with pytest.raises(ValueError):
        nominal_gaps(angle_deg=float('nan'))

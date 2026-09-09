import pytest
from probe_vrm_right_extent import right_extent


def test_rectangle_and_translation():
    p=[[0,0],[10,0],[10,12],[0,12]]
    assert right_extent(p)['lower_third_rightmost_px']==10
    assert right_extent([[x+3,y] for x,y in p])['lower_third_rightmost_px']==13


def test_cut_intersection():
    assert right_extent([[0,0],[12,0],[0,12]])['lower_third_rightmost_px']==pytest.approx(4)


def test_degenerate():
    with pytest.raises(ValueError):
        right_extent([[0,0],[1,0],[2,0]])

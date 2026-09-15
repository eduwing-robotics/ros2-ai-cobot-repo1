import pytest
from socket_footprint import compare_footprint

S = [[0,0],[10,0],[10,10],[0,10]]

def test_inside_and_touch_are_not_pass():
    for p in ([[1,1],[9,1],[9,9],[1,9]], S):
        r=compare_footprint(S,p)
        assert r['measured_outline_inside'] and r['status']=='UNKNOWN'

def test_center_inside_corner_outside():
    r=compare_footprint(S,[[5,-1],[11,5],[5,11],[-1,5]])
    assert r['maximum_exit']==pytest.approx(1)
    assert not r['measured_outline_inside']

def test_order_and_units():
    p=[[9,2],[12,2],[12,5],[9,5]]
    assert compare_footprint(S[::-1],p)['maximum_exit']==pytest.approx(2)
    assert compare_footprint([[x*2,y*2] for x,y in S],
                             [[x*2,y*2] for x,y in p])['maximum_exit']==pytest.approx(4)

@pytest.mark.parametrize('p',[None,[],[[0,0],[1,1],[2,2]],[[0,0],[1,1],[float('nan'),2]]])
def test_invalid(p):
    assert compare_footprint(S,p)['reason']=='INVALID_OR_MISSING_POLYGON'

def test_nonconvex_rejected():
    assert compare_footprint([[0,0],[10,0],[5,5],[10,10],[0,10]], S)['reason']=='NONCONVEX_SOCKET_UNSUPPORTED'

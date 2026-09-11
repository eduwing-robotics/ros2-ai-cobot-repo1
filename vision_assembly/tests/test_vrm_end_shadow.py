from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from vrm_edge_refinement import inner_end_peak,measure

@pytest.mark.parametrize('sign',[-1,1])
def test_inner_edge_wins_over_stronger_outer_shadow(sign):
    x=np.arange(23)
    v=16*np.exp(-.5*((x-7)/.8)**2)+19*np.exp(-.5*((x-14)/.8)**2)
    if sign==-1:v=v[::-1]
    assert inner_end_peak(v,sign)==pytest.approx(7 if sign==1 else 15,abs=.01)

@pytest.mark.parametrize('sign',[-1,1])
def test_weak_interior_texture_is_not_an_edge(sign):
    x=np.arange(23);v=2*np.exp(-.5*((x-3)/.7)**2)+18*np.exp(-.5*((x-10)/.8)**2)
    if sign==-1:v=v[::-1]
    assert inner_end_peak(v,sign)==pytest.approx(10 if sign==1 else 12,abs=.01)

@pytest.mark.parametrize('values',[np.zeros(13),np.ones(13),np.arange(13),np.full(13,np.nan)])
def test_flat_boundary_and_invalid_profiles_rejected(values):
    with pytest.raises(ValueError):inner_end_peak(values,1)

def test_four_edges_recover_object_center_with_column_varying_shadow():
    image=np.full((720,1280,3),210,np.uint8)
    image[315:323,489:512]=100
    image[285:315,489:512]=30
    # shadow contrast alternates, so a global argmax would mix two boundaries.
    for x in range(494,507):image[315:323,x]=100+(x%3)*12
    d=dict(center_pixel=[500,300],depth_m=.5,base_xyz_mm=[0,0,0])
    result=measure(image,d,[900,0,640,0,900,360,0,0,1],np.eye(4))
    assert result['center_pixel']==pytest.approx([500,299.5],abs=.25)

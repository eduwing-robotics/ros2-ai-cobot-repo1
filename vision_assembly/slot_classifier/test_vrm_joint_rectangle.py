import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from probe_vrm_joint_rectangle import joint_rectangle


def line(intercept,slope=0,strength=10):
    return dict(slope=slope,intercept=intercept,strength=strength,support=9)


def test_joint_rejects_incoherent_strong_edge():
    options=[[line(20,.25,20),line(20,0,10)],[line(30)],[line(120)],[line(170)]]
    r=joint_rectangle(options)
    assert r['measurement_available']
    assert r['candidate']['center_px']==[70,100]
    assert r['status']=='UNKNOWN'


def test_two_rectangles_are_unknown():
    r=joint_rectangle([[line(20),line(30)],[line(30)],[line(120)],[line(170)]])
    assert not r['measurement_available']
    assert r['reason']=='COMPETING_RECTANGLES'


def test_missing_edge():
    assert not joint_rectangle([[],[line(30)],[line(120)],[line(170)]])['measurement_available']

import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from vrm_line_pose_evidence import polygon_from_edges,pose_evidence


def edges():
    return [dict(candidate=dict(slope=0.,intercept=float(v)),ambiguous=False) for v in (20,30,120,170)]


def test_center_and_angle():
    r=polygon_from_edges(edges())
    np.testing.assert_allclose(r['center_px'],[70,100])
    assert r['angle_deg']==0


def test_rotated_rectangle():
    angle=np.deg2rad(8)
    rotation=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    p=np.array([[-50,-70],[50,-70],[50,70],[-50,70]])@rotation.T+[80,110]
    lines=[]
    for i,(a,b) in enumerate([(0,3),(0,1),(1,2),(3,2)]):
        axis=1 if i%2==0 else 0
        slope=(p[b,1-axis]-p[a,1-axis])/(p[b,axis]-p[a,axis])
        lines.append(dict(candidate=dict(slope=slope,intercept=p[a,1-axis]-slope*p[a,axis]),ambiguous=False))
    r=polygon_from_edges(lines)
    np.testing.assert_allclose(r['center_px'],[80,110])
    assert abs(r['angle_deg']-8)<1e-8


def test_ambiguity_has_no_center():
    r=pose_evidence(dict(reasons=['COMPETING_LINES']*4,raw=edges(),clahe=edges()))
    assert r['status']=='UNKNOWN' and not r['measurement_available']
    assert 'center_px' not in r


def test_crossed_edges_rejected():
    e=edges()
    e[0]['candidate']['intercept']=140
    assert polygon_from_edges(e) is None


def test_inconsistent_angles_rejected():
    e=edges()
    e[0]['candidate']['slope']=.2
    assert polygon_from_edges(e) is None

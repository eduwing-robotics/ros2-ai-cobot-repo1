from copy import deepcopy
from types import SimpleNamespace as NS
from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vrm_refinement_window as module
from vrm_refinement_window import VrmRefinementWindow,RecaptureRequired,matched_evidence

Q={'minimum_observation_frames':20,'parts':{'black_block':dict(minimum_detection_confidence=.7,minimum_mask_shape_score=.8,minimum_rectangularity=.8)}}
def payload(stamp):
    return {'timestamp_ros_ns':stamp*10**9,'stable_detections':[
        dict(part_type='black_block',instance_index=i,reference_center_pixel=[100.*i,100.],base_xyz_mm=[10.*i,0.,0.],
             observation_frames=40,median_detection_confidence=.9,median_mask_shape_score=.9,median_rectangularity=.9)
        for i in range(1,6)]}
def snapshot():return {'tray_capture':{'parts':deepcopy(payload(0)['stable_detections'])}}
def fit(image,d,k,t):return dict(center_base_mm=d['base_xyz_mm'],base_angle_deg=90.)
def message(stamp):return NS(header=NS(stamp=NS(sec=stamp,nanosec=0)))

def test_exact_image_detection_and_intrinsics_are_required():
    old=message(10);new=message(11)
    assert matched_evidence([old,new],[old,new],10*10**9,after=9,now=11.2)==(old,old)
    assert matched_evidence([new],[old,new],10*10**9,after=9,now=11.2) is None
    assert matched_evidence([old],[new],10*10**9,after=9,now=11.2) is None
    assert matched_evidence([old],[old],10*10**9,after=9,now=12.1) is None


def test_twelve_distinct_matched_frames_required(monkeypatch):
    monkeypatch.setattr(module,'measure',fit);w=VrmRefinementWindow(snapshot(),Q)
    for i in range(1,12):
        assert not w.observe(None,payload(i),None,None)
        assert not w.observe(None,payload(i),None,None)
    assert w.observe(None,payload(12),None,None)
    assert all(v['refinement_frame_count']==12 for v in w.accepted.values())


def test_failed_fit_cannot_reuse_accepted_part_to_complete(monkeypatch):
    monkeypatch.setattr(module,'measure',fit);w=VrmRefinementWindow(snapshot(),Q)
    for i in range(1,13):
        p=payload(i);p['stable_detections'][-1]['median_detection_confidence']=.5
        assert not w.observe(None,p,None,None)
    def later(image,d,k,t):
        if d['instance_index']==1:raise ValueError('edge disagreement')
        return fit(image,d,k,t)
    monkeypatch.setattr(module,'measure',later)
    for i in range(13,25):assert not w.observe(None,payload(i),None,None)
    assert len(w.accepted)==5
    assert 1 in w.pending()


def test_weak_geometry_is_pending_but_strong_change_requires_full_recapture(monkeypatch):
    monkeypatch.setattr(module,'measure',fit);w=VrmRefinementWindow(snapshot(),Q)
    p=payload(1);p['stable_detections'][0]['base_xyz_mm'][2]=3.
    p['stable_detections'][0]['median_detection_confidence']=.4
    assert not w.observe(None,p,None,None)
    p['timestamp_ros_ns']=2*10**9;p['stable_detections'][0]['median_detection_confidence']=.9
    with pytest.raises(RecaptureRequired,match='dXYZ'):w.observe(None,p,None,None)
    assert 1 not in w.accepted


def test_identity_change_is_not_recapturable(monkeypatch):
    monkeypatch.setattr(module,'measure',fit);w=VrmRefinementWindow(snapshot(),Q)
    p=payload(1);p['stable_detections'][0]['reference_center_pixel'][0]+=20
    with pytest.raises(RuntimeError,match='identity changed') as error:w.observe(None,p,None,None)
    assert not isinstance(error.value,RecaptureRequired)

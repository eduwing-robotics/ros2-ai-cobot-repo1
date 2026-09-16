import cv2
import numpy as np
from gpu_surface_crack import inspect_gpu_crack


def sample():
    a = np.full((600,320,3),65,np.uint8)
    cv2.rectangle(a,(125,230),(200,285),(30,180,30),-1)
    cv2.putText(a,'GPU',(110,325),cv2.FONT_HERSHEY_SIMPLEX,.7,(230,230,230),2)
    return a


def test_visible_transverse_ridge_candidate_and_no_pass_authority():
    a = sample()
    cv2.line(a,(135,405),(195,405),(10,10,10),4)
    r = inspect_gpu_crack(a,'PRESENT',True)
    assert r.status == 'FAIL' and r.authority == 'ADVISORY_ONLY'
    assert r.measured['candidates']
    assert r.measured['certifies_physical_crack'] is False
    assert inspect_gpu_crack(sample(),'PRESENT',True).status == 'UNKNOWN'


def test_diagonal_print_texture_not_transverse_crack():
    a = sample()
    for offset in range(-100,300,18):
        cv2.line(a,(90,350+offset),(230,490+offset),(40,40,40),1)
    assert inspect_gpu_crack(a,'PRESENT',True).status == 'UNKNOWN'


def test_missing_alignment_presence_logo_abstain():
    assert inspect_gpu_crack(sample(),'EMPTY',True).status == 'UNKNOWN'
    assert inspect_gpu_crack(sample(),'PRESENT',False).status == 'UNKNOWN'
    assert inspect_gpu_crack(np.full((600,320,3),65,np.uint8),'PRESENT',True).status == 'UNKNOWN'


def test_saved_current_defect_replays_when_installed():
    from pathlib import Path
    import pytest
    root = Path(__file__).resolve().parents[2]/'runtime/inspection/hybrid_fixed_slot'
    paths = [root/n/'fixed_slots/gpu/ai_gpu.png' for n in (
        '20260914_201154_859671','20260914_201837_148806',
        '20260914_202207_020385','20260914_202531_682221')]
    if not all(p.is_file() for p in paths):
        pytest.skip('Local development captures unavailable')
    for p in paths:
        e = inspect_gpu_crack(cv2.imread(str(p)),'PRESENT',True)
        assert e.status == 'FAIL', str(p)
        assert any(230 < c['bbox_crop_px'][0] < 300 and 630 < c['bbox_crop_px'][1] < 680
                   for c in e.measured['candidates']), str(p)


def test_pin_and_crack_categories_coexist_without_api_identifier_change():
    from main import build_advisory_candidates
    a = sample()
    cv2.line(a,(135,405),(195,405),(10,10,10),4)
    from dataclasses import asdict
    row = dict(slot_id='ai_gpu', component_type='GPU', stages={
        'presence': dict(status='UNKNOWN', predicted_state='PRESENT', authority='ADVISORY_ONLY'),
        'pose': dict(status='UNKNOWN', measured={}, limits={}),
        'orientation': dict(status='UNKNOWN'),
        'surface': dict(status='UNKNOWN', score=None, fail_min=None),
        'pins': dict(status='FAIL', reason='GPU_WHITE_PIN_PATTERN_DEFECT'),
        'surface_crack': asdict(inspect_gpu_crack(a,'PRESENT',True))})
    c = build_advisory_candidates([row])[0]
    assert c['codes'] == ['PINS?', 'SURFACE?']
    assert c['crack_regions_crop_px']
    assert 'GPU_TRANSVERSE_DARK_CRACK_CANDIDATE' in c['details']
    assert c['authority'] == 'ADVISORY_ONLY'

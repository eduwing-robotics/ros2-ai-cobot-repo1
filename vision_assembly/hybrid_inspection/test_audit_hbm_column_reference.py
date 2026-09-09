import numpy as np
import pytest
from audit_hbm_column_reference import compare_columns


def scene():
    rgb = np.zeros((240,170,3),np.uint8)
    for x in (45,130):
        for y in range(30,160,18):
            rgb[y:y+4,x:x+3] = 220
    return rgb


def test_removed_first_anchor_does_not_move_reference():
    ref = scene()
    sample = ref.copy()
    sample[30:34,130:133] = 0
    result = compare_columns(ref,sample)['right']
    assert result['reason'] == 'REFERENCE_WHITE_DEFICIT_CANDIDATE'
    assert result['near_absent_xy_px'] == [[131.,31.5]]
    assert result['status'] == 'UNKNOWN'
    assert np.array_equal(ref, scene())


def test_identical_not_certified_pass():
    assert all(s['status']=='UNKNOWN' and s['reason']=='NO_NEAR_ABSENCE_AT_TESTED_ANCHORS'
               for s in compare_columns(scene(),scene()).values())


def test_darkness_abstains():
    assert all(s['reason']=='SAMPLE_SUPPORT_UNRESOLVED'
               for s in compare_columns(scene(),np.zeros_like(scene())).values())


def test_shape_mismatch():
    with pytest.raises(ValueError):
        compare_columns(scene(), scene()[:200])


def test_lateral_probe_keeps_missing_endpoint():
    ref=scene()
    sample=np.zeros_like(ref)
    sample[:,6:]=ref[:,:-6]
    sample[30:34,136:139]=0
    result=compare_columns(ref,sample,lateral_probe=True)['right']
    assert result['lateral_probe_dx_px']==pytest.approx(6)
    assert result['near_absent_xy_px']==[[131.,31.5]]
    assert result['reference_y_locked']
    assert result['status']=='UNKNOWN'


def test_lateral_probe_refuses_one_sided_fit():
    sample=scene()
    sample[:,:80]=0
    assert all(s['reason']=='PAIRED_COLUMN_SHIFT_UNRESOLVED'
               for s in compare_columns(scene(),sample,lateral_probe=True).values())

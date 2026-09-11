from copy import deepcopy
from audit_component_bias_modes import without_bias


def test_counterfactual_does_not_change_source_or_pixel_geometry():
    rows=[dict(slot_id='hbm_01',stages=dict(pose=dict(confidence=.9,
        measured=dict(raw_offset_mm=[1.,0.],center_px=[500.,600.],
            expected_center_px=[490.,600.],axis_angle_deg=90.),
        limits=dict(expected_axis_angle_deg=90.,position_tolerance_mm=.75,
                    angle_tolerance_deg=3.))))]
    original=deepcopy(rows)
    result=without_bias(rows)
    assert rows==original
    pose=result[0]['stages']['pose']
    assert pose['status']=='FAIL' and pose['authority']=='ADVISORY_ONLY'
    assert pose['measured']['center_px']==[500.,600.]
    assert pose['measured']['common_bias_correction_mm']==[0.,0.]


def test_missing_pose_evidence_is_not_filled_in():
    rows=[dict(slot_id='hbm_01',stages=dict(pose=dict(status='UNKNOWN')))]
    assert without_bias(rows)==rows

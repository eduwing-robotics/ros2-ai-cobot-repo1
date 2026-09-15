import copy
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tray_home_gate import HOME,check_inventory,add_inspections,check_pick_removal
from full_cycle_motion import build_canonical_slot_waypoints


def data():
    p=dict(part_type='hbm',instance_index=3,base_xyz_mm=[1.,2.,3.],long_axis_angle_base_deg=0.)
    ref=dict(handeye_sha256='test',parts=[p],bindings=[dict(part_type='hbm',physical_index=3,reference_center_pixel=[10,20])])
    d=dict(p,reference_center_pixel=[10,20],observation_frames=20,
           median_detection_confidence=.9,median_mask_shape_score=.9,median_rectangularity=.9)
    live=dict(timestamp_ros_ns=100_000_000_000,handeye_sha256='test',tray_registration='TRACKING',
              base_transform_status='OK',stable_detections=[d])
    quality=dict(minimum_observation_frames=20,parts={'hbm':dict(minimum_detection_confidence=.55,minimum_mask_shape_score=.45,minimum_rectangularity=.45)})
    return live,ref,quality


def test_present_and_removed_evidence():
    live,ref,q=data()
    assert check_inventory(live,ref,set(),q,101,99)['remaining_slots']==['HBM-03']
    with pytest.raises(RuntimeError,match='inventory'):
        check_inventory(live,ref,{'HBM-03'},q,101,99)
    live['stable_detections']=[]
    result=check_inventory(live,ref,{'HBM-03'},q,101,99)
    assert result['evidence']=='tray_inventory_only_not_holding_proof'


@pytest.mark.parametrize('change,match',[
    ({'reference_center_pixel':[99,20]},'identity'),
    ({'base_xyz_mm':[5,2,3]},'XY'),
    ({'long_axis_angle_base_deg':10},'axis'),
    ({'median_detection_confidence':.2},'quality'),
    ({'base_xyz_mm':[float('nan'),2,3]},'XY'),
])
def test_changed_or_low_quality_target_blocks(change,match):
    live,ref,q=data();live['stable_detections'][0].update(change)
    with pytest.raises(RuntimeError,match=match):check_inventory(live,ref,set(),q,101,99)


def test_stale_and_changed_calibration_block():
    live,ref,q=data()
    with pytest.raises(RuntimeError,match='fresh'):check_inventory(live,ref,set(),q,103,99)
    live['handeye_sha256']='changed'
    with pytest.raises(RuntimeError,match='handeye'):check_inventory(live,ref,set(),q,101,99)


def test_inspection_departs_directly_for_board_without_pick_hover_return():
    start=[36,-449,321,180,0,180]
    raw=build_canonical_slot_waypoints(start,[-560,-40,-47,180,0,90],[62,-526,92,180,0,180],350)
    route=add_inspections([('HBM-03',w) for w in raw],start)
    labels=[w.label for _,w in route]
    assert not any(label.startswith('tray_before') for label in labels)
    assert route[0][1]==raw[0]
    after=labels.index('tray_after_inspect')
    assert route[after][1].tcp==HOME
    assert 'tray_after_restore' not in labels
    assert 'tray_after_return' not in labels
    assert 'carry_safe_vertical' not in labels[after:]
    transfer=labels.index('place_combined_xy_abc')
    assert all(w.tcp[2] == 350 for _,w in route[after+1:transfer+1])
    assert route[after+1][1].tcp[:2] == HOME[:2]
    assert route[transfer][1].tcp == next(w.tcp for w in raw if w.label=='place_combined_xy_abc')
    assert labels.index('tray_after_inspect')<labels.index('place_final_50mm_vertical')


def test_pick_only_gate_ignores_other_section_confidence():
    live,ref,q=data()
    live['stable_detections']=[dict(part_type='long_orange',median_detection_confidence=.01)]
    assert check_pick_removal(live,ref,{'HBM-03'},'HBM-03',101,99)['picked_slot']=='HBM-03'


def test_pick_only_gate_rejects_target_still_present_even_weak():
    live,ref,q=data();live['stable_detections'][0]['median_detection_confidence']=.01
    with pytest.raises(RuntimeError,match='occupied'):
        check_pick_removal(live,ref,{'HBM-03'},'HBM-03',101,99)


def test_no_detections_does_not_prove_pick():
    live,ref,q=data();live['stable_detections']=[]
    with pytest.raises(RuntimeError,match='no visual'):
        check_pick_removal(live,ref,{'HBM-03'},'HBM-03',101,99)


def test_last_part_requires_fresh_registered_empty_tray_and_all_reference_cells_removed():
    live,ref,_=data()
    live.update(stable_detections=[],detections=[],detected_total=0,stable_detected_total=0,
                registration_source='shared_section_tracker',registration_age_ms=100,
                robot_pose_span_mm=.01,robot_rotation_span_deg=.001,depth_sync_ms=60)
    assert check_pick_removal(live,ref,{'HBM-03'},'HBM-03',101,99)['picked_slot']=='HBM-03'
    ref['bindings'].append(dict(part_type='right_white_brown',physical_index=5,reference_center_pixel=[50,50]))
    with pytest.raises(RuntimeError,match='no visual'):
        check_pick_removal(live,ref,{'HBM-03'},'HBM-03',101,99)
    live['registration_age_ms']=501
    with pytest.raises(RuntimeError,match='no visual'):
        check_pick_removal(live,ref,{'HBM-03','CAP-05'},'HBM-03',101,99)

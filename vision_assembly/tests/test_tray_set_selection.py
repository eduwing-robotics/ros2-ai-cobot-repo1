from copy import deepcopy
from pathlib import Path
import json
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tray_set_selection import select_cycle_tray_set
from tray_capture_retry import TrayCaptureRetry
from fixed_cycle_snapshot import EXPECTED_TRAY_COUNTS
from tray_home_gate import check_pick_removal, check_inventory

def frame():
    return json.loads((Path(__file__).parent/'fixtures/two_set_registered_tray.json').read_text())

def quality():
    return json.loads((Path(__file__).resolve().parents[1]/'config/part_gripper_recipes.json').read_text())['tray_snapshot_quality']

def reference(selected):
    return dict(handeye_sha256=selected['handeye_sha256'],
        assembly_set_selection=selected['assembly_set_selection'],
        parts=selected['stable_detections'],
        bindings=[dict(part_type=d['part_type'],physical_index=d['instance_index'],
                       reference_center_pixel=d['reference_center_pixel'])
                  for d in selected['stable_detections']])

def test_full_two_sets_select_exact_original_first_set_and_keep_source_ids():
    raw=frame();original=deepcopy(raw)
    result=select_cycle_tray_set(raw)
    assert raw==original
    assert len(result['stable_detections'])==25
    for kind,count in EXPECTED_TRAY_COUNTS.items():
        actual=[d for d in result['stable_detections'] if d['part_type']==kind]
        expected=[d for d in raw['stable_detections'] if d['part_type']==kind and d['instance_index']<=count]
        assert [d['reference_center_pixel'] for d in actual]==[d['reference_center_pixel'] for d in expected]
        assert [d.get('id') for d in actual]==[d.get('id') for d in expected]

def test_second_set_can_be_empty_without_changing_first_set():
    raw=frame();selected=select_cycle_tray_set(raw)
    raw['stable_detections']=[d for d in raw['stable_detections'] if d['instance_index']<=EXPECTED_TRAY_COUNTS[d['part_type']]]
    assert select_cycle_tray_set(raw)['stable_detections']==selected['stable_detections']

@pytest.mark.parametrize('kind',list(EXPECTED_TRAY_COUNTS))
def test_missing_first_set_part_never_borrows_from_second(kind):
    raw=frame()
    raw['stable_detections']=[d for d in raw['stable_detections'] if not (d['part_type']==kind and d['instance_index']==1)]
    result=select_cycle_tray_set(raw)
    assert sum(d['part_type']==kind for d in result['stable_detections'])==EXPECTED_TRAY_COUNTS[kind]-1
    collector=TrayCaptureRetry(quality(),after=100,defer_smd_to_close_view=True)
    for stamp in range(101,105):
        result['timestamp_ros_ns']=stamp*1e9
        assert collector.observe(result,stamp+.1) is None

def test_boundary_and_duplicate_are_rejected():
    raw=frame();gpu=next(d for d in raw['stable_detections'] if d['part_type']=='gpu')
    gpu['reference_center_pixel'][0]=800
    with pytest.raises(RuntimeError,match='boundary'):select_cycle_tray_set(raw)
    raw=frame()
    gpu=[d for d in raw['stable_detections'] if d['part_type']=='gpu']
    gpu[1]['reference_center_pixel']=gpu[0]['reference_center_pixel'][:]
    with pytest.raises(RuntimeError,match='extra'):select_cycle_tray_set(raw)

def test_actual_capture_retry_accepts_selected_twenty_five():
    collector=TrayCaptureRetry(quality(),after=100,defer_smd_to_close_view=True)
    for stamp in range(101,105):
        selected=select_cycle_tray_set(frame());selected['timestamp_ros_ns']=stamp*1e9
        result=collector.observe(selected,stamp+.1)
    assert result is not None
    assert len(result['stable_detections'])==25
    assert result['assembly_set_selection']['set_index']==1

def test_pick_removal_with_second_gpu_present_and_no_false_removal():
    raw=frame();selected=select_cycle_tray_set(raw);ref=reference(selected)
    raw['timestamp_ros_ns']=101e9
    with pytest.raises(RuntimeError,match='occupied'):
        check_pick_removal(raw,ref,{'GPU-01'},'GPU-01',101.1,100)
    raw['stable_detections']=[d for d in raw['stable_detections'] if not (d['part_type']=='gpu' and d['instance_index']==1)]
    result=check_pick_removal(raw,ref,{'GPU-01'},'GPU-01',101.1,100)
    assert result['picked_slot']=='GPU-01'

def test_inventory_with_full_second_set_preserves_geometric_checks():
    raw=frame();ref=reference(select_cycle_tray_set(raw));raw['timestamp_ros_ns']=101e9
    result=check_inventory(raw,ref,set(),quality(),101.1,100)
    assert len(result['remaining_slots'])==19
    target=next(d for d in raw['stable_detections'] if d['part_type']=='hbm')
    target['base_xyz_mm'][0]+=10
    with pytest.raises(RuntimeError,match='XY changed'):
        check_inventory(raw,ref,set(),quality(),101.1,100)

import copy
import json
from pathlib import Path
import sys
import cv2
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/scripts'))
from full_cycle_plan import build_plan
from vrm_edge_refinement import measure, summarize, merge, SOURCE
FIX=Path(__file__).parent/'fixtures/validated_20260907'
def read(path):return json.loads(path.read_text())
def recipes():return read(ROOT/'vision_assembly/config/part_gripper_recipes.json')
def slots():return read(ROOT/'vision_assembly/config/assembly_slots_r1.json')

@pytest.mark.parametrize('slot',['PM-03','PM-04'])
def test_production_pm_reproduces_operator_confirmed_target(slot):
    fixture=read(FIX/(slot+'.json'))
    item=build_plan(fixture['snapshot'],recipes(),slots(),selected_slots=[slot])['plan'][0]
    # Sept 7 fixture predates the operator-requested Sept 8 PM lowering.
    # Preserve the measured fixture; apply only the explicitly approved Z delta.
    expected = list(fixture['expected'])
    expected[2] -= 0.5
    assert recipes()['parts']['long_orange']['board_place_z_adjustment_mm'] == -0.5
    assert item['place_final_tcp']==pytest.approx(expected,abs=1e-6)
    assert item['placement_orientation']['rotation_skipped_in_plan'] is False
    moved=copy.deepcopy(fixture['snapshot'])
    moved['resolved_placements'][slot]['corrected_place_xy_base_mm'][0]+=10
    fresh=build_plan(moved,recipes(),slots(),selected_slots=[slot])['plan'][0]
    assert fresh['place_final_tcp'][0]==pytest.approx(item['place_final_tcp'][0]+10)

def test_vrm_photograph_reproduces_tested_four_edge_measurement():
    f=read(FIX/'VRM-02.json');image=cv2.imread(str(FIX/'VRM-02.jpg'))
    result=measure(image,f['detection'],f['k'],np.array(f['T_base_flange'])@np.array(f['T_flange_camera']))
    expected=f['expected_sample']
    assert result['center_pixel']==pytest.approx(expected['four_edge_center_pixel'],abs=1e-6)
    assert result['center_base_mm']==pytest.approx(expected['four_edge_center_base_mm'],abs=.002)
    assert result['base_angle_deg']==pytest.approx(expected['base_angle_deg'],abs=.002)
    with pytest.raises(ValueError):measure(np.zeros_like(image),f['detection'],f['k'],np.eye(4))

def test_vrm_window_rejects_angular_motion():
    f=read(FIX/'VRM-02.json')
    samples=[dict(center_base_mm=p['four_edge_center_base_mm'],base_angle_deg=p['base_angle_deg']) for p in f['samples']]
    result=summarize(samples)
    assert result['base_xyz_mm']==pytest.approx(f['expected_part']['base_xyz_mm'])
    samples[-1]['base_angle_deg']+=4
    with pytest.raises(ValueError,match='unstable'):summarize(samples)

def test_refinement_preserves_cells_and_correction_applied_once():
    snapshot=read(ROOT/'vision_assembly/data/fixed_cycle_full_restart_retry2_2026-09-02.json')
    parts=[p for p in snapshot['tray_capture']['parts'] if p['part_type']=='black_block']
    for p in parts:p['reference_center_pixel']=[100+p['instance_index']*40,150]
    refinements={p['instance_index']:dict(base_xyz_mm=p['base_xyz_mm'],long_axis_angle_base_deg=1.,angle_source=SOURCE,refinement_frame_count=12) for p in parts}
    refined=merge(snapshot,refinements,123.)
    for original,p in zip(parts,[p for p in refined['tray_capture']['parts'] if p['part_type']=='black_block']):
        assert p['reference_center_pixel']==original['reference_center_pixel']
    refined['authorized_selected_slots']=['VRM-01']
    refined['tray_capture']['parts']=[p for p in refined['tray_capture']['parts'] if p['part_type']=='black_block' and p['instance_index']==1]
    item=build_plan(refined,recipes(),slots(),selected_slots=['VRM-01'])['plan'][0]
    assert item['pick_final_tcp'][5]==pytest.approx(91.)
    assert np.array(item['pick_final_tcp'][:2])-item['tray_surface_base_mm'][:2]==pytest.approx([-1.5164288635806775,1.5898010636828328])
    assert (item['tray_open_position'],item['grip_position'],item['release_position'])==(30,24,28)
    del refinements[5]
    with pytest.raises(ValueError,match='five'):merge(snapshot,refinements,123.)


def test_smd_coarse_presence_never_authorizes_a_pick():
    snapshot=read(ROOT/'vision_assembly/data/fixed_cycle_full_restart_retry2_2026-09-02.json')
    snapshot['smd_close_captured']=True
    for p in snapshot['tray_capture']['parts']:
        if p['part_type']=='right_white_brown':p['deferred_to_smd_close']=True
    with pytest.raises(RuntimeError,match='SMDView validation required'):
        build_plan(snapshot,recipes(),slots(),phase='smd')


def test_all_vrm_grasps_keep_tested_branch_after_previous_board_placement():
    snapshot=read(ROOT/'vision_assembly/data/fixed_cycle_full_restart_retry2_2026-09-02.json')
    angles=[2.061,.282,2.536,.069,-1.334]
    for p in snapshot['tray_capture']['parts']:
        if p['part_type']=='black_block':
            p['long_axis_angle_base_deg']=angles[p['instance_index']-1]
            p['angle_source']=SOURCE
    items=build_plan(snapshot,recipes(),slots(),phase='non-smd')['plan']
    vrms=[p for p in items if p['part_type']=='black_block']
    assert [p['pick_final_tcp'][5] for p in vrms]==pytest.approx([90+a for a in angles])
    assert all(p['place_final_tcp'][5]<-170 for p in vrms)
    assert all(p['pick_correction_base_mm']==pytest.approx([-1.5164288635806775,1.5898010636828328]) for p in vrms)

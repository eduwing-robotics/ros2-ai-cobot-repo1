from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml
from std_msgs.msg import String
from vision_server.orchestration_contract import ContractFailure
from vision_server.unity_calibration_contract import board_state, tray_state, BoardWindow
from vision_server.unity_calibration_server import UnityCalibrationServer
from test_conveyor_stop_lease import lease_fixture, ready
from test_orchestration_contract import pcb_payload, tray_payload, PART_MAPPINGS

ROOT=Path(__file__).resolve().parents[4]
CONFIG=yaml.safe_load((ROOT/'ros2_ws/src/vision_server/config/orchestration_api.yaml').read_text())['orchestration_api']
GEOMETRY={key:json.loads((ROOT/path).read_text()) for key,path in {
    'board':'vision_assembly/config/physical_board.json',
    'slots':'vision_assembly/config/assembly_slots_r1.json',
    'residual':'vision_assembly/config/assembly_placecamera_residual.json'}.items()}


def source(stamp=10_000_000_000):
    data=pcb_payload(stamp)
    T=np.asarray(data['T_base_board'])
    residual=np.array(GEOMETRY['residual']['residual_base_mm'])
    data['slots']={s['slot_code']:{'surface_base_mm':
        ((T@np.array([s['x_mm']/1000,s['y_mm']/1000,0,1]))[:3]*1000+residual).tolist()}
        for s in GEOMETRY['slots']['slots']}
    return data


def state(stamp=10_000_000_000):
    return board_state(source(stamp),CONFIG['pcb'],GEOMETRY,now_ns=stamp+100_000_000)


def test_all_25_slot_local_positions_reconstruct_tracker_base_with_one_residual():
    data=state();T=np.array(data['T_base_board'])
    assert data['slot_count']==25
    assert data['board_size_m']==pytest.approx([.139,.110])
    assert data['board_pose']['position_m']==pytest.approx([.1,-.2,.3])
    for slot in data['slots']:
        reconstructed=(T@np.r_[slot['board_position_m'],1])[:3]
        assert reconstructed==pytest.approx(slot['base_position_m'])
        nominal=(T@np.r_[slot['nominal_board_position_m'],1])[:3]
        assert reconstructed-nominal==pytest.approx(data['residual_base_m'])
        assert np.linalg.norm(slot['base_orientation_xyzw'])==pytest.approx(1)
    assert data['robot_motion_authorized'] is False


def test_board_rejects_mixed_slot_geometry():
    payload=source();payload['slots']['GPU-01']['surface_base_mm'][0]+=.1
    with pytest.raises(ContractFailure,match='geometry'):board_state(payload,CONFIG['pcb'],GEOMETRY,now_ns=10_100_000_000)


@pytest.mark.parametrize('change',[
    lambda p:p.update(valid=False),
    lambda p:p.update(hole_fit_rms_mm=3),
    lambda p:p.update(timestamp_ros_ns=1),
    lambda p:p.update(timestamp_ros_ns=11_000_000_000),
    lambda p:p['slots'].pop('CAP-05'),
    lambda p:p['T_base_board'][0].__setitem__(0,2),
])
def test_invalid_quality_stale_future_missing_slot_and_bad_rotation_rejected(change):
    payload=source();change(payload)
    with pytest.raises(ContractFailure):board_state(payload,CONFIG['pcb'],GEOMETRY,now_ns=10_100_000_000)


def test_window_requires_four_distinct_post_request_frames():
    window=BoardWindow();sample=state()
    for _ in range(10):window.observe(sample)
    assert not window.stable()
    for i in range(1,4):window.observe(state(10_000_000_000+i*100_000_000))
    assert window.stable()
    assert not window.stable(now_ns=13_000_000_000)
    assert not window.stable(after_ns=10_000_000_000)
    assert window.stable(after_ns=9_999_999_999)
    moved=state(10_400_000_000);moved['T_base_board'][0][3]+=.002
    window.observe(moved);assert not window.stable()
    window.clear();assert not window.stable()


def test_tray_preserves_physical_ids_and_section_reference_not_targets():
    layout=json.loads((ROOT/'vision_assembly/config/tray_layout_candidate.json').read_text())
    data=tray_state(tray_payload(),{'part_mappings':PART_MAPPINGS,'minimum_observation_frames':5},layout,now_ns=10_100_000_000)
    assert [p['id'] for p in data['parts']]==['gpu:01','hbm:01','hbm:02']
    assert data['parts'][0]['position_m']==pytest.approx([.1,-.2,.05])
    assert data['section_reference']['reference_only']
    assert len(data['section_reference']['sections'])==len(layout['bins'])


class FakePublisher:
    def __init__(self):self.messages=[]
    def publish(self,msg):self.messages.append(json.loads(msg.data))


def fake_server():
    from collections import OrderedDict
    server=object.__new__(UnityCalibrationServer)
    server.config=CONFIG;server.pending={};server.completed=OrderedDict()
    server.reply=FakePublisher();server.preview=FakePublisher();server.window=BoardWindow()
    server.publisher_id='test';server.sequence=0
    server.conveyor_lease,server.heartbeat_clock=lease_fixture()
    ready(server.conveyor_lease,server.heartbeat_clock)
    server.get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=10_500_000_000))
    server._board_snapshot=lambda:state(10_400_000_000)
    server._tray_snapshot=lambda:{'valid':True,'schema':'test_tray'}
    return server


def request(action='getBoardSnapshot',id='request1'):
    return dict(request_id=id,job_id='job1',action=action,
                product_code=CONFIG['pcb']['expected_product_code'],
                product_version=CONFIG['pcb']['expected_product_version'])


def test_request_response_correlation_and_duplicate_idempotency():
    server=fake_server()
    for i in range(4):server.window.observe(state(10_100_000_000+i*100_000_000))
    req=request();server._request(String(data=json.dumps(req)));server._tick()
    reply=server.reply.messages[-1]
    assert reply['success'] and reply['request_id']=='request1' and reply['job_id']=='job1'
    assert reply['data']['slot_count']==25
    server._request(String(data=json.dumps(req)))
    assert server.reply.messages[-1]==reply
    req['action']='calibrateBoard';server._request(String(data=json.dumps(req)))
    assert server.reply.messages[-1]['error_code']=='INVALID_REQUEST'


def test_calibrate_requires_new_frames_and_conveyor_confirmation():
    server=fake_server()
    server.heartbeat_clock.advance(.2)
    server.conveyor_lease.observe(False,server.heartbeat_clock.info())
    server._request(String(data=json.dumps(request('calibrateBoard'))))
    for i in range(4):server.window.observe(state(10_600_000_000+i*100_000_000))
    server._board_snapshot=lambda:state(10_900_000_000)
    server.pending['request1']['deadline']=0
    server._tick()
    assert not server.reply.messages[-1]['success']
    assert server.reply.messages[-1]['error_code']=='CONVEYOR_NOT_STOPPED'


@pytest.mark.parametrize('change', ['expire', 'false', 'restart'])
def test_pending_calibration_does_not_survive_a_lost_stop_session(change):
    server=fake_server()
    server._request(String(data=json.dumps(request('calibrateBoard'))))
    clock=server.heartbeat_clock
    clock.advance(1.01 if change=='expire' else .2)
    if change=='false':server.conveyor_lease.observe(False,clock.info())
    if change=='restart':ready(server.conveyor_lease,clock,writer=2)
    for i in range(4):server.window.observe(state(10_600_000_000+i*100_000_000))
    server._board_snapshot=lambda:state(10_900_000_000)
    server._tick()
    assert 'request1' not in server.pending
    assert server.reply.messages[-1]['error_code']=='CONVEYOR_NOT_STOPPED'
    assert server.reply.messages[-1]['success'] is False


def test_calibrate_accepts_new_stable_frames_while_stop_session_is_live():
    server=fake_server()
    server._request(String(data=json.dumps(request('calibrateBoard'))))
    for i in range(4):server.window.observe(state(10_600_000_000+i*100_000_000))
    server.get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=11_000_000_000))
    server._board_snapshot=lambda:state(10_900_000_000)
    server._tick()
    assert server.reply.messages[-1]['success'] is True
    assert server.reply.messages[-1]['robot_motion_authorized'] is False


def test_acquiring_initial_stop_evidence_requires_new_frames_after_acquisition():
    server=fake_server()
    clock=server.heartbeat_clock
    clock.advance(.2)
    server.conveyor_lease.observe(False,clock.info())
    server._request(String(data=json.dumps(request('calibrateBoard'))))
    for i in range(4):server.window.observe(state(10_600_000_000+i*100_000_000))
    server.get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=11_000_000_000))
    server._board_snapshot=lambda:state(10_900_000_000)
    clock.advance(.2)
    ready(server.conveyor_lease,clock)
    server._tick()
    assert server.reply.messages == []
    assert server.pending['request1']['after_ns'] == 11_000_000_000
    for i in range(4):server.window.observe(state(11_100_000_000+i*100_000_000))
    server.get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=11_500_000_000))
    server._board_snapshot=lambda:state(11_400_000_000)
    server._tick()
    assert server.reply.messages[-1]['success'] is True


def test_pose_guard_rejects_wrong_camera_pose_and_prearrival_frames():
    import time
    server=fake_server();server.robot=object();server.robot_received=time.monotonic();server.view_since={}
    with pytest.raises(ContractFailure,match='PlaceCamera'):server._pose_guard('PlaceCamera',source())
    server.view_since['PlaceCamera']=10_000_000_000
    with pytest.raises(ContractFailure,match='post-arrival'):server._pose_guard('PlaceCamera',source())
    server._pose_guard('PlaceCamera',source(12_100_000_000))


def test_invalid_preview_marks_stale_without_replaying_old_valid_geometry():
    server=fake_server()
    def failed():raise ContractFailure('CAMERA_POSE_NOT_READY','not PlaceCamera')
    server._board_snapshot=failed
    server._tick()
    preview=server.preview.messages[-1]
    assert not preview['valid'] and preview['timestamp_ros_ns'] is None
    assert 'slots' not in preview

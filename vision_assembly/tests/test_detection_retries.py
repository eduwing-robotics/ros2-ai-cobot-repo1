import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from capture_smd_with_retries import capture_with_retries
from test_merge_smd_retry_captures import capture
import tray_home_gate as gate


def smd_runner(results, calls):
    def run(command, **kwargs):
        calls.append(command)
        code, payload = results[len(calls)-1]
        if payload is not None:
            Path(command[-1]).write_text(json.dumps(payload))
        return SimpleNamespace(returncode=code)
    return run


def test_smd_complements_independently_passing_parts(tmp_path):
    calls=[]
    result=capture_with_retries(tmp_path/'result.json', now=lambda:120,
        runner=smd_runner([(2,capture(100,2)),(2,capture(110,1))],calls))
    assert len(calls)==2 and result['validation_passed']
    assert result['timestamp_unix']==100
    assert result['detection_attempts']==2


def test_smd_timeout_discards_prior_partial_coordinates(tmp_path):
    calls=[]
    result=capture_with_retries(tmp_path/'result.json',now=lambda:120,
        runner=smd_runner([(2,capture(100,2)),(3,None),(2,capture(110,1)),(0,capture(115,0))],calls))
    assert len(calls)==4
    assert all('attempt_4' in v['file'] for v in result['retry_sources'].values())


@pytest.mark.parametrize('failure', ['hardware','moved','exhausted'])
def test_smd_no_targets_after_failure(tmp_path,failure):
    calls=[]
    moved=capture(110,1);moved['parts'][0]['part_center_base_mm'][0]+=1
    results=([(1,None)] if failure=='hardware' else
             [(2,capture(100,2)),(2,moved)] if failure=='moved' else [(3,None)]*4)
    with pytest.raises(RuntimeError):
        capture_with_retries(tmp_path/'result.json',now=lambda:120,runner=smd_runner(results,calls))
    assert not (tmp_path/'result.json').exists()
    assert len(calls)==len(results)


def test_smd_never_accepts_existing_output(tmp_path):
    path=tmp_path/'result.json';path.write_text('{}')
    with pytest.raises(RuntimeError,match='already exists'):
        capture_with_retries(path,runner=lambda *a,**k:pytest.fail('must not run'))


def inspection_setup(tmp_path,monkeypatch,accept_after=0,safety=None):
    from execute_cached_hbm_remaining import Executor
    clock=SimpleNamespace(value=100.,frames=0)
    path=tmp_path/'live.json'
    monkeypatch.setattr(gate.time,'time',lambda:clock.value)
    monkeypatch.setattr(gate.time,'monotonic',lambda:clock.value)
    def spin(node,timeout_sec):
        clock.value+=1;clock.frames+=1
        node.state_cb(node.state)
        path.write_text(json.dumps({'timestamp_ros_ns':int(clock.value*1e9)}))
    monkeypatch.setattr(gate.rclpy,'spin_once',spin)
    monkeypatch.setattr(gate.rclpy,'ok',lambda:True)
    def check(live,reference,removed,slot,now,arrived):
        if clock.frames<=accept_after:
            raise RuntimeError('picked cell still occupied')
        assert live['timestamp_ros_ns']/1e9>arrived
        return {'timestamp_ros_ns':live['timestamp_ros_ns']}
    monkeypatch.setattr(gate,'check_pick_removal',check)
    node=object.__new__(Executor)
    node.state=SimpleNamespace(robot_motion_done=1)
    node.state_sequence=0
    node.state_received_monotonic=0.0
    node.safety_error=lambda state:safety
    return node,path,clock


def test_inspection_retries_fresh_frames_then_passes(tmp_path,monkeypatch):
    node,path,clock=inspection_setup(tmp_path,monkeypatch,accept_after=5)
    result=gate.wait_inventory(node,path,{},set(),{},timeout=5,picked_slot='HBM-01')
    assert result['detection_attempts']==2
    assert result['distinct_consecutive_frames']==3
    assert result['previous_attempt_reasons']==['picked cell still occupied']


def test_inspection_exhausts_without_motion_or_false_success(tmp_path,monkeypatch):
    node,path,clock=inspection_setup(tmp_path,monkeypatch,accept_after=100)
    with pytest.raises(RuntimeError,match='exhausted'):
        gate.wait_inventory(node,path,{},set(),{},timeout=5,picked_slot='HBM-01')
    assert clock.frames==15


def test_inspection_hardware_error_stops_immediately(tmp_path,monkeypatch):
    node,path,clock=inspection_setup(tmp_path,monkeypatch,safety='collision')
    with pytest.raises(RuntimeError,match='collision'):
        gate.wait_inventory(node,path,{},set(),{},timeout=5,picked_slot='HBM-01')
    assert clock.frames==1

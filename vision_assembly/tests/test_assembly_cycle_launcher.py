from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import assembly_cycle_launcher as launcher
import cycle_camera_stage as camera


def save(path, value):
    path.write_text(json.dumps(value))


def completed_record(directory, phase):
    slots = launcher.NON_SMD if phase == 'non-smd' else launcher.SMD
    plan = directory / f'{phase}_plan.json'
    save(plan, {'cycle_id': 'test-cycle'})
    record = {'status': 'motion_complete_awaiting_physical_verification',
              'motion_completed_slots': slots, 'selected_slots': slots,
              'part_held_candidate': False, 'cycle_id': 'test-cycle',
              'plan_sha256': hashlib.sha256(plan.read_bytes()).hexdigest()}
    save(directory / f'{phase}_run.json', record)
    return record


def test_general_phase_explicitly_inspects_and_smd_uses_fresh_close_capture(tmp_path):
    steps = dict(launcher.workflow(tmp_path))
    for mode in ('preflight', 'assemble'):
        assert '--verify-tray-pick' in steps[f'{mode}_non-smd']
        assert '--verify-tray-pick' not in steps[f'{mode}_smd']
    assert any(Path(arg).name == 'capture_smd_with_retries.py' for arg in steps['measure_smd'])
    assert str(tmp_path / 'smd_close.json') in steps['merge_smd']
    names = list(steps)
    assert names.index('assemble_non-smd') < names.index('capture_smd_view') < names.index('assemble_smd')


@pytest.mark.parametrize('mutation', [
    {'status': 'paused_after_grasp_verification_required'},
    {'motion_completed_slots': launcher.NON_SMD[:-1]},
    {'part_held_candidate': True},
    {'held_slot': 'IND-02'},
    {'cycle_id': 'another-cycle'},
    {'plan_sha256': '0' * 64},
])
def test_incomplete_or_wrong_run_cannot_enter_smd(tmp_path, mutation):
    record = completed_record(tmp_path, 'non-smd')
    record.update(mutation)
    save(tmp_path / 'non-smd_run.json', record)
    with pytest.raises(RuntimeError, match='완료 기록'):
        launcher.verify_completion(tmp_path, 'non-smd')


@pytest.mark.parametrize('phase', ['non-smd', 'smd'])
def test_complete_matching_phase_is_accepted(tmp_path, phase):
    completed_record(tmp_path, phase)
    launcher.verify_completion(tmp_path, phase)


@pytest.mark.parametrize('key,stamp', [
    ('board_capture', 100), ('tray_capture', float('nan')),
    ('smd_close_capture', 8000), ('smd_close_capture', 10001),
])
def test_stale_missing_nonfinite_or_future_capture_rejected(tmp_path, key, stamp):
    payload = {name: {'captured_unix': 9990} for name in ('board_capture', 'tray_capture', 'smd_close_capture')}
    payload[key]['captured_unix'] = stamp
    save(tmp_path / 'snapshot.json', payload)
    with pytest.raises(RuntimeError, match='촬영'):
        launcher.verify_capture_ages(tmp_path, 'smd', now=10000)


def fake_phase_runner(directory, fail_at=None, incomplete=False):
    called = []
    def runner(command, log):
        name = log.stem
        called.append(name)
        if name == fail_at:
            raise RuntimeError('simulated failure')
        if name == 'capture_tray':
            save(directory / 'snapshot.json', {
                name: {'captured_unix': time.time()} for name in ('board_capture', 'tray_capture')})
        if name == 'refine_vrm':
            payload = launcher.read(directory / 'snapshot.json')
            payload['vrm_refinement_capture'] = {'captured_unix': time.time()}
            save(directory / 'snapshot.json', payload)
        if name == 'merge_smd':
            payload = launcher.read(directory / 'snapshot.json')
            payload['smd_close_capture'] = {'captured_unix': time.time()}
            save(directory / 'snapshot.json', payload)
        if name.startswith('assemble_'):
            phase = name.split('_', 1)[1]
            record = completed_record(directory, phase)
            if incomplete:
                record['motion_completed_slots'] = []
                save(directory / f'{phase}_run.json', record)
    return runner, called


@pytest.mark.parametrize('fail_at', ['stack_check', 'capture_board', 'refine_vrm', 'preflight_non-smd', 'assemble_non-smd', 'measure_smd', 'preflight_smd'])
def test_stage_failure_never_starts_successor(tmp_path, monkeypatch, fail_at):
    monkeypatch.setattr(launcher, 'check_installation', lambda: {})
    runner, called = fake_phase_runner(tmp_path, fail_at=fail_at)
    with pytest.raises(RuntimeError, match='simulated'):
        launcher.run_cycle(tmp_path, {}, runner)
    assert called[-1] == fail_at
    record = launcher.read(tmp_path / 'cycle.json')
    assert record['status'] == 'stopped_on_error'
    assert record['steps'][-1]['status'] == 'failed'


def test_child_exit_zero_with_incomplete_motion_stops_sequence(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, 'check_installation', lambda: {})
    runner, called = fake_phase_runner(tmp_path, incomplete=True)
    with pytest.raises(RuntimeError, match='완료 기록'):
        launcher.run_cycle(tmp_path, {}, runner)
    assert called[-1] == 'assemble_non-smd'
    assert 'capture_smd_view' not in called


def test_two_complete_phases_do_not_claim_physical_placement(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, 'check_installation', lambda: {})
    runner, called = fake_phase_runner(tmp_path)
    launcher.run_cycle(tmp_path, {}, runner)
    record = launcher.read(tmp_path / 'cycle.json')
    assert len(called) == 15
    assert record['status'] == 'motion_complete_awaiting_physical_verification'
    assert record['physical_placement_verified'] is False


@pytest.mark.parametrize('start,target,name', [
    ([35,-450,320,180,0,180], [-528,-61,338,-180,0,90], 'TrayHome'),
    ([-528,-61,338,-180,0,90], [37,-449,321,180,0,180], 'PlaceCamera'),
    ([100,-500,190,-180,0,90], [-528,-121,78,180,0,90], 'SMDView'),
])
def test_camera_routes_retract_before_fixed_height_transit(start, target, name):
    route = camera.camera_route(start, target, name)
    preceding = start
    for _, waypoint in route:
        if waypoint.linear:
            assert waypoint.tcp[:2] == tuple(preceding[:2])
            assert waypoint.tcp[3:] == tuple(preceding[3:])
        else:
            assert waypoint.tcp[2] == preceding[2] >= 350
        if waypoint.label == 'place_final_50mm_vertical':
            assert 0 <= preceding[2] - waypoint.tcp[2] <= 50
        preceding = waypoint.tcp
    assert route[-1][1].tcp == tuple(target)


@pytest.mark.parametrize('stamp', [99.0, 101.0, 107.0, float('nan')])
def test_prearrival_stale_future_frames_rejected(stamp):
    with pytest.raises(RuntimeError, match='fresh'):
        camera.require_fresh_frame({'timestamp_ros_ns': stamp * 1e9}, after=100, now=106)


def test_fresh_frame_and_stable_board_window():
    assert camera.require_fresh_frame({'timestamp_ros_ns': 105e9}, after=100, now=106) == 105
    samples = [{'T_base_board': [[1,0,0,0], [0,1,0,0], [0,0,1,z], [0,0,0,1]]} for z in [0,0.0001,0.0002,0.0001]]
    assert camera.board_window_valid(samples)
    samples[-1]['T_base_board'][2][3] = 0.01
    assert not camera.board_window_valid(samples)


def test_runner_streams_and_records_output(tmp_path, capsys):
    launcher.run_step([sys.executable, '-c', 'print("progress")'], tmp_path / 'child.log', timeout=5)
    assert 'progress' in capsys.readouterr().out
    assert (tmp_path / 'child.log').read_text() == 'progress\n'


def test_runner_timeout_interrupts_child_before_next_stage(tmp_path):
    with pytest.raises(subprocess.TimeoutExpired):
        launcher.run_step([sys.executable, '-c', 'import time; time.sleep(10)'], tmp_path / 'child.log', timeout=0.2)


def test_duplicate_result_aging_does_not_clear_consecutive_capture_window():
    # Producer latency 1.3s and result interval 1.5s recreate the live failure:
    # accepted frames become >2s old before the next file is published.
    samples = []
    last = None
    for stamp in [101.0, 102.5, 104.0, 105.5]:
        payload = {'timestamp_ros_ns': stamp * 1e9}
        result = camera.next_frame_stamp(payload, last, after=100, now=stamp + 1.3)
        assert result == stamp
        samples.append(result)
        last = result
        assert camera.next_frame_stamp(payload, last, after=100, now=stamp + 2.4) is None
    assert len(samples) == 4


def test_distinct_stale_result_is_still_rejected():
    with pytest.raises(RuntimeError, match='age=3.000s'):
        camera.next_frame_stamp({'timestamp_ros_ns': 104e9}, 102.5, after=100, now=107)


def test_duplicate_stream_is_not_counted_as_multiple_frames():
    last = camera.next_frame_stamp({'timestamp_ros_ns': 101e9}, None, after=100, now=102)
    for now in [102.1, 103, 105, 160]:
        assert camera.next_frame_stamp({'timestamp_ros_ns': 101e9}, last, after=100, now=now) is None


@pytest.mark.parametrize('error', [RuntimeError('motion fault'), KeyboardInterrupt()])
def test_motion_fault_or_interrupt_always_requests_stop(error):
    assert camera.stop_required_after_failure(True, error, lambda: True)


def test_exhausted_vision_retry_at_verified_pose_does_not_latch_stop():
    assert not camera.stop_required_after_failure(True, camera.RetryCaptureError('exhausted'), lambda: True)


def test_vision_failure_with_pose_drift_or_lost_feedback_still_requests_stop():
    error=camera.RetryCaptureError('exhausted')
    assert camera.stop_required_after_failure(True,error,lambda: False)
    def unavailable():raise RuntimeError('state lost')
    assert camera.stop_required_after_failure(True,error,unavailable)


def test_capture_only_never_sends_stop_motion():
    assert not camera.stop_required_after_failure(False,RuntimeError('capture failed'),lambda: False)


@pytest.mark.parametrize('start_c', [180.,-180.,179.9999,-179.9999,180.0001,-180.0001])
def test_placecamera_to_trayhome_wraps_midpoint_euler_for_controller(start_c):
    start=[36.944,-449.134,321.342,179.999,.001,start_c]
    target=[-527.997,-60.954,337.880,-180.,0.,90.]
    route=camera.camera_route(start,target,'TrayHome')
    assert all(-180<=a<=180 for _,w in route for a in w.tcp[3:])
    mids=[w for _,w in route if w.label=='place_combined_xy_abc_midpoint']
    assert len(mids)==2
    assert mids[0].tcp[5]==pytest.approx(150,abs=.001)
    assert mids[1].tcp[5]==pytest.approx(120,abs=.001)


@pytest.mark.parametrize('start_c', [180.,-180.,179.9999,-179.9999,180.0001,-180.0001])
def test_restart_at_placecamera_does_not_expand_feedback_noise_to_full_turn(start_c):
    start=[36.944,-449.134,321.342,179.999,.001,start_c]
    target=[36.943,-449.135,321.342,179.998,.001,180.]
    route=camera.camera_route(start,target,'PlaceCamera')
    mids=[w for _,w in route if w.label=='place_combined_xy_abc_midpoint']
    assert len(mids)==2
    assert all(abs((w.tcp[5]-180+180)%360-180)<.001 for w in mids)


def test_vrm_refinement_precedes_general_planning(tmp_path):
    names=list(dict(launcher.workflow(tmp_path)))
    assert names.index('capture_tray')<names.index('refine_vrm')<names.index('plan_non-smd')


def test_missing_vrm_refinement_blocks_general_execution(tmp_path):
    save(tmp_path/'snapshot.json', {name:{'captured_unix':9990} for name in ('board_capture','tray_capture')})
    with pytest.raises(RuntimeError,match='vrm_refinement_capture'):
        launcher.verify_capture_ages(tmp_path,'non-smd',now=10000)


def test_reviewed_config_hash_rejects_unreviewed_change(tmp_path, monkeypatch):
    relative='vision_assembly/config/part_gripper_recipes.json'
    config=tmp_path/relative;config.parent.mkdir(parents=True);config.write_text('{}')
    baseline=tmp_path/'baseline';old=baseline/'files'/relative;old.parent.mkdir(parents=True);old.write_text('{"old":true}')
    revision=tmp_path/'revision.json'
    save(revision,{'schema':'fr5.assembly_launcher_revision/v1','reviewed_config_sha256':{relative:'0'*64}})
    monkeypatch.setattr(launcher,'ROOT',tmp_path);monkeypatch.setattr(launcher,'BASELINE',baseline)
    monkeypatch.setattr(launcher,'REVISION',revision);monkeypatch.setattr(launcher,'BASELINE_FILES',(relative,))
    with pytest.raises(RuntimeError,match='설정'):
        launcher.check_installation()


def test_smd_deferral_only_enabled_at_trayhome():
    steps=dict(launcher.workflow(Path('/tmp/test-cycle')))
    assert '--defer-smd-to-close-view' in steps['capture_tray']
    assert '--defer-smd-to-close-view' not in steps['capture_board']
    assert any(Path(arg).name == 'capture_smd_with_retries.py' for arg in steps['measure_smd'])


@pytest.mark.parametrize('start_c', [-178.696, -178.5, -175., 175., 90., 0.])
def test_placecamera_return_never_adds_full_turn(start_c):
    start=[9., -498., 190., 180., 0., start_c]
    target=[36.943, -449.135, 321.342, 179.998, .001, 180.]
    route=camera.camera_route(start,target,'PlaceCamera')
    angles=[start_c]+[w.tcp[5] for _,w in route]
    travel=sum(abs((b-a+180)%360-180) for a,b in zip(angles,angles[1:]))
    assert travel == pytest.approx(abs((180-start_c+180)%360-180))
    assert all(abs((b-a+180)%360-180)<=60.00001 for a,b in zip(angles,angles[1:]))


def test_direct_launcher_sets_udp_for_children(monkeypatch):
    import os
    monkeypatch.setenv('FASTDDS_BUILTIN_TRANSPORTS','DEFAULT')
    monkeypatch.setattr(sys,'argv',['launcher','--dry-run'])
    monkeypatch.setattr(launcher,'check_installation',lambda: {})
    launcher.main()
    assert os.environ['FASTDDS_BUILTIN_TRANSPORTS']=='UDPv4'

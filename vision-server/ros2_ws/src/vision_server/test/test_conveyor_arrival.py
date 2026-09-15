"""Offline temporal evidence tests: no ROS initialization or motor commands."""
import pytest
from vision_server.conveyor_arrival import (
    LiveArrival,
    arrival_matches,
    empty_matches,
    restart_empty_matches,
)


BASE = 10_000_000_000


def motor(now, **updates):
    state = dict(timestamp_ns=now, state='ASSEMBLY_STOP', moving=False,
                 command_linear_x_mps=0.0, server_instance_id='server', motion_id='server:1')
    state.update(updates)
    return state


def feed(tracker, index, value=None, **motor_updates):
    now = BASE + index * 50_000_000
    tracker.set_motor(motor(now, **motor_updates), now)
    values = [[0., 200., 300., 100., 80.]] if value is None else value
    tracker.observe(now, now, {'assembly': values, 'inspection': []})
    return now


def stable():
    tracker = LiveArrival()
    for i in range(9):
        now = feed(tracker, i)
    return tracker, now


def test_fresh_stable_evidence_and_other_station_unknown():
    tracker, now = stable()
    result = tracker.snapshot('assembly', now)
    assert result['at_station'] and result['stable_frames'] == 9
    assert not tracker.snapshot('inspection', now)['at_station']
    assert arrival_matches(result, 'assembly', now, .15, 'server', 'server:1', 'ASSEMBLY_STOP')
    for station, server, movement, state in [('inspection','server','server:1','ASSEMBLY_STOP'),
        ('assembly','restarted','server:1','ASSEMBLY_STOP'),
        ('assembly','server','server:2','ASSEMBLY_STOP'),
        ('assembly','server','server:1','MOVING_TO_ASSEMBLY')]:
        assert not arrival_matches(result, station, now, .15, server, movement, state)


def test_camera_silence_expires_without_any_new_image():
    tracker, now = stable()
    assert not tracker.snapshot('assembly', now+151_000_000)['at_station']
    # A fresh motor status must not revive a stale image or its old history.
    tracker.set_motor(motor(now+160_000_000), now+160_000_000)
    assert not tracker.snapshot('assembly', now+160_000_000)['at_station']


@pytest.mark.parametrize('value', [[], [[9.,200.,300.,100.,80.]],
    [[0.,200.,300.,100.,80.]]*2, [[float('nan'),200.,300.,100.,80.]]])
def test_missing_outside_ambiguous_invalid_board_immediately_withdraws(value):
    tracker, _ = stable()
    now = feed(tracker, 9, value)
    assert not tracker.snapshot('assembly', now)['at_station']
    now = feed(tracker, 10)
    assert not tracker.snapshot('assembly', now)['at_station']


@pytest.mark.parametrize('updates', [dict(moving=True), dict(command_linear_x_mps=.01),
    dict(state='FAULT'), dict(state='MANUAL_STOP'), dict(command_linear_x_mps=float('nan'))])
def test_motor_motion_fault_or_unknown_prevents_arrival(updates):
    tracker, _ = stable()
    now = feed(tracker, 9, **updates)
    assert not tracker.snapshot('assembly', now)['at_station']
    if updates.get('state') == 'MANUAL_STOP':
        assert tracker.snapshot('assembly', now)['reason'] == 'MOTOR_STATE_MANUAL_STOP'


def test_motion_drift_is_compared_with_whole_window_not_only_last_frame():
    tracker = LiveArrival()
    for i in range(30):
        now = feed(tracker, i, [[0.,200.+i*.5,300.,100.,80.]])
        assert not tracker.snapshot('assembly', now)['at_station']


def test_repeated_image_does_not_count_and_invalid_frame_resets_history():
    tracker, now = stable()
    tracker.observe(now, now, {'assembly': [[0.,200.,300.,100.,80.]]})
    assert not tracker.snapshot('assembly', now)['at_station']
    now = feed(tracker, 9)
    assert not tracker.snapshot('assembly', now)['at_station']
    tracker.invalidate('DECODE_FAILED')
    assert not tracker.snapshot('assembly', now)['at_station']


def test_pause_restart_or_gap_requires_new_stability_window():
    tracker, _ = stable()
    for i, updates in [(9, dict(server_instance_id='new')), (20, {})]:
        now = feed(tracker, i, **updates)
        assert not tracker.snapshot('assembly', now)['at_station']


def test_nested_state_cannot_create_feedback_payload_growth():
    tracker = LiveArrival()
    tracker.set_motor(motor(BASE, live_arrival={'recursive': 'data'}), BASE)
    assert 'live_arrival' not in tracker.motor


@pytest.mark.parametrize('options', [dict(minimum_frames=1), dict(tolerance_px=float('inf')),
    dict(stationary_span_px=0), dict(minimum_seconds=-1)])
def test_invalid_limits_are_rejected(options):
    with pytest.raises(ValueError):
        LiveArrival(**options)


def test_empty_requires_positive_background_and_two_seconds_of_distinct_frames():
    t = LiveArrival()
    for i in range(41):
        now = BASE+i*50_000_000
        t.set_motor(motor(now), now)
        t.observe(now, now, {'assembly': [], 'inspection': []}, regions_clear=True)
        assert t.snapshot('assembly', now)['regions_empty'] == (i == 40)
    t.observe(now, now, {'assembly': [], 'inspection': []}, regions_clear=True)
    assert not t.snapshot('assembly', now)['regions_empty']
    for i in range(41, 90):
        now = BASE+i*50_000_000
        t.set_motor(motor(now), now)
        t.observe(now, now, {'assembly': [], 'inspection': []})
    assert not t.snapshot('assembly', now)['regions_empty']


def test_restart_empty_evidence_is_shorter_than_passive_cleanup_window():
    t = LiveArrival()
    for i in range(9):
        now = BASE+i*50_000_000
        t.set_motor(motor(now), now)
        t.observe(now, now, {'assembly': [], 'inspection': []}, regions_clear=True)
    payload = t.snapshot('assembly', now)
    assert payload['restart_regions_empty']
    assert not payload['regions_empty']
    assert payload['restart_empty_frames'] == 9
    assert restart_empty_matches(
        payload, 'assembly', now, .15, 'server', 'server:1', 'ASSEMBLY_STOP'
    )
    assert not empty_matches(
        payload, 'assembly', now, .15, 'server', 'server:1', 'ASSEMBLY_STOP'
    )

    # A single obstructed frame withdraws both forms of empty evidence.
    t.observe(now + 50_000_000, now + 50_000_000,
              {'assembly': [[0., 200., 300., 100., 80.]], 'inspection': []},
              regions_clear=False)
    payload = t.snapshot('assembly', now + 50_000_000)
    assert not payload['restart_regions_empty'] and not payload['regions_empty']


def test_manual_stop_can_accumulate_empty_retry_evidence_but_never_arrival():
    t = LiveArrival()
    for i in range(9):
        now = BASE+i*50_000_000
        t.set_motor(motor(now, state='MANUAL_STOP'), now)
        t.observe(now, now, {'assembly': [], 'inspection': []}, regions_clear=True)
    payload = t.snapshot('assembly', now)
    assert payload['restart_regions_empty']
    assert not payload['at_station']
    assert payload['reason'] == 'MOTOR_STATE_MANUAL_STOP'


def test_empty_camera_expiry_and_obstruction_withdraw_immediately():
    t = LiveArrival()
    for i in range(41):
        now = BASE+i*50_000_000
        t.set_motor(motor(now), now)
        t.observe(now, now, {'assembly': [], 'inspection': []}, regions_clear=True)
    assert t.snapshot('inspection', now)['regions_empty']
    assert not t.snapshot('inspection', now+151_000_000)['regions_empty']


def test_clear_region_rejects_board_bright_occlusion_darkness_and_missing_image():
    import numpy as np
    from vision_server.conveyor_arrival import clear_belt_region
    image = np.full((100, 200, 3), 135, dtype=np.uint8)
    assert clear_belt_region(image, .1, .9, .2, .8)
    for value in (20, 250, 0):
        bad = image.copy(); bad[30:70, 50:150] = value
        assert not clear_belt_region(bad, .1, .9, .2, .8)
    assert not clear_belt_region(None, .1, .9, .2, .8)


def test_clear_region_can_exclude_only_a_verified_upstream_polygon():
    import numpy as np
    from vision_server.conveyor_arrival import clear_belt_region
    image = np.full((100, 200, 3), 135, dtype=np.uint8)
    image[30:70, 50:150] = 20
    assert not clear_belt_region(image, .1, .9, .2, .8)
    assert clear_belt_region(
        image, .1, .9, .2, .8,
        ignore_polygons=[np.asarray([[50, 30], [150, 30], [150, 70], [50, 70]])],
    )
    # Ignoring almost the whole belt is rejected instead of becoming a false
    # empty result.
    assert not clear_belt_region(
        image, .1, .9, .2, .8,
        ignore_polygons=[np.asarray([[0, 0], [199, 0], [199, 99], [0, 99]])],
    )

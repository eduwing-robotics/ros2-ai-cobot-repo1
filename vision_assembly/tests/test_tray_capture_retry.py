from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from fixed_cycle_snapshot import EXPECTED_TRAY_COUNTS
from tray_capture_retry import TrayCaptureRetry, RetryCaptureError

QUALITY = {'minimum_observation_frames': 4, 'parts': {
    kind: {'minimum_detection_confidence': .7, 'minimum_mask_shape_score': .8,
           'minimum_rectangularity': .8} for kind in EXPECTED_TRAY_COUNTS}}


def frame(stamp):
    parts = []
    for kind, count in EXPECTED_TRAY_COUNTS.items():
        for i in range(1, count + 1):
            parts.append({'part_type': kind, 'instance_index': i,
                          'reference_center_pixel': [i*50., 100.], 'base_xyz_mm': [i*20., 0., 0.],
                          'long_axis_angle_base_deg': 0., 'observation_frames': 8,
                          'median_detection_confidence': .9, 'median_mask_shape_score': .95,
                          'median_rectangularity': .95})
    return {'timestamp_ros_ns': stamp*1e9, 'tray_registration': 'TRACKING',
            'base_transform_status': 'VALID_COORDINATES_ONLY', 'handeye_sha256': 'a'*64,
            'stable_detections': parts}


def part(payload, kind='long_orange', index=1):
    return next(p for p in payload['stable_detections'] if p['part_type']==kind and p['instance_index']==index)


def test_only_failed_part_retried_and_good_parts_preserved_with_original_time():
    collector = TrayCaptureRetry(QUALITY, after=100)
    for stamp in range(101,105):
        payload=frame(stamp);part(payload)['median_detection_confidence']=.69
        assert collector.observe(payload, stamp+.2) is None
    assert len(collector.accepted)==24
    frozen = deepcopy(collector.accepted[('hbm',1)])
    for stamp in range(116,120):
        payload=frame(stamp)
        # Previously accepted HBM may flicker in confidence; geometry remains fixed.
        part(payload,'hbm')['median_detection_confidence']=.6
        result=collector.observe(payload,stamp+.2)
    assert result is not None
    assert collector.accepted[('hbm',1)]==frozen
    assert part(result,'hbm')['median_detection_confidence']==.9
    assert result['oldest_part_capture_unix']==104
    assert result['per_part_capture_sources']['long_orange:1']['accepted_attempt']==2
    assert result['per_part_capture_sources']['long_orange:1']['source_timestamp_unix']==119


def test_duplicate_frames_do_not_advance_quality_streak():
    collector=TrayCaptureRetry(QUALITY,after=100)
    collector.observe(frame(101),101.2)
    for now in [101.3,103.5,108]:
        assert collector.observe(frame(101),now) is None
    assert not collector.accepted
    assert set(collector.streak.values())=={1}


def test_pending_bad_observation_resets_only_its_own_streak():
    collector=TrayCaptureRetry(QUALITY,after=100)
    for stamp in range(101,105):
        payload=frame(stamp)
        if stamp==103:part(payload)['median_detection_confidence']=.69
        collector.observe(payload,stamp+.2)
    assert len(collector.accepted)==24
    assert collector.streak[('long_orange',1)]==1


def test_missing_part_does_not_shift_canonical_identity():
    collector=TrayCaptureRetry(QUALITY,after=100)
    collector.observe(frame(101),101.2)
    for stamp in range(102,106):
        payload=frame(stamp)
        payload['stable_detections'].remove(part(payload))
        for p in payload['stable_detections']:
            if p['part_type']=='long_orange':p['instance_index']-=1
        assert collector.observe(payload,stamp+.2) is None
    assert ('long_orange',1) not in collector.accepted
    assert collector.accepted[('long_orange',2)]['detection']['base_xyz_mm']==[40.,0.,0.]
    for stamp in range(106,110):result=collector.observe(frame(stamp),stamp+.2)
    assert result is not None
    assert part(result,index=1)['base_xyz_mm']==[20.,0.,0.]


def test_no_identity_is_inferred_from_initial_incomplete_class():
    collector=TrayCaptureRetry(QUALITY,after=100)
    for stamp in range(101,105):
        payload=frame(stamp);payload['stable_detections'].remove(part(payload))
        collector.observe(payload,stamp+.2)
    assert all(k[0]!='long_orange' for k in collector.accepted)
    assert len(collector.accepted)==21


@pytest.mark.parametrize('change', ['move','rotate','registration','hash','extra'])
def test_scene_or_identity_changes_do_not_reuse_cached_geometry(change):
    collector=TrayCaptureRetry(QUALITY,after=100)
    for stamp in range(101,105):
        first=frame(stamp);part(first)['median_detection_confidence']=.5
        collector.observe(first,stamp+.2)
    payload=frame(105)
    if change=='move':part(payload,'hbm')['base_xyz_mm'][0]+=3
    if change=='rotate':part(payload,'hbm')['long_axis_angle_base_deg']=4
    if change=='registration':payload['tray_registration']='NOT_REGISTERED'
    if change=='hash':payload['handeye_sha256']='b'*64
    if change=='extra':payload['stable_detections'].append(deepcopy(part(payload)))
    with pytest.raises(RetryCaptureError):collector.observe(payload,105.2)


def test_retry_limit_names_unresolved_part_without_skipping_it():
    collector=TrayCaptureRetry(QUALITY,after=100)
    for stamp in range(101,160):
        payload=frame(stamp);part(payload)['median_detection_confidence']=.65
        assert collector.observe(payload,stamp+.1) is None
    assert len(collector.accepted)==24
    with pytest.raises(RetryCaptureError,match='initial \\+ 3 retries; long_orange:1'):
        collector.tick(160)


def test_missing_previously_accepted_part_blocks_completion():
    collector=TrayCaptureRetry(QUALITY,after=100)
    for stamp in range(101,105):
        payload=frame(stamp);part(payload)['median_detection_confidence']=.5
        collector.observe(payload,stamp+.2)
    for stamp in range(105,109):
        payload=frame(stamp);payload['stable_detections'].remove(part(payload,'gpu'))
        assert collector.observe(payload,stamp+.2) is None
    assert len(collector.accepted)==25
    assert 'gpu:1' in collector.report()['pending']


def test_new_stale_observation_cannot_pass():
    collector=TrayCaptureRetry(QUALITY,after=100)
    with pytest.raises(RuntimeError,match='fresh'):
        collector.observe(frame(101),104)


def test_real_recipe_warmup_does_not_anchor_noisy_four_frame_geometry():
    quality=deepcopy(QUALITY);quality['minimum_observation_frames']=20
    collector=TrayCaptureRetry(quality,after=100)
    for stamp,count in [(101,4),(102,8),(103,12),(104,16)]:
        payload=frame(stamp)
        for p in payload['stable_detections']:p['observation_frames']=count
        # The actual failure: early VRM XYZ/axis settles beyond motion limits.
        part(payload,'black_block')['base_xyz_mm'][2]=stamp-100
        part(payload,'black_block')['long_axis_angle_base_deg']=(stamp-100)*5
        assert collector.observe(payload,stamp+.2) is None
        assert collector.anchors=={}
        assert collector.geometry_candidates=={}
    for stamp in range(105,109):
        payload=frame(stamp)
        for p in payload['stable_detections']:p['observation_frames']=20
        result=collector.observe(payload,stamp+.2)
    assert result is not None
    assert len(collector.accepted)==25


def test_low_confidence_geometry_never_becomes_a_motion_reference():
    collector=TrayCaptureRetry(QUALITY,after=100)
    payload=frame(101);part(payload,'black_block')['median_detection_confidence']=.6
    part(payload,'black_block')['long_axis_angle_base_deg']=20
    collector.observe(payload,101.2)
    assert ('black_block',1) not in collector.geometry_candidates
    for stamp in range(102,106):result=collector.observe(frame(stamp),stamp+.2)
    assert result is not None


def test_unconfirmed_geometry_change_resets_only_pending_streak():
    collector=TrayCaptureRetry(QUALITY,after=100)
    collector.observe(frame(101),101.2)
    for stamp in range(102,106):
        payload=frame(stamp);part(payload,'black_block')['long_axis_angle_base_deg']=5
        result=collector.observe(payload,stamp+.2)
    assert result is not None
    assert collector.accepted[('black_block',1)]['source_timestamp_unix']==105


def test_weak_changed_observation_of_confirmed_part_blocks_completion_without_false_motion():
    collector=TrayCaptureRetry(QUALITY,after=100)
    for stamp in range(101,105):
        payload=frame(stamp);part(payload)['median_detection_confidence']=.6
        collector.observe(payload,stamp+.2)
    payload=frame(105);part(payload,'black_block')['median_detection_confidence']=.5
    part(payload,'black_block')['long_axis_angle_base_deg']=15
    assert collector.observe(payload,105.2) is None
    assert ('black_block',1) not in collector.current_visible
    assert collector.accepted[('black_block',1)]['detection']['long_axis_angle_base_deg']==0


def test_smd_presence_can_defer_confidence_but_not_shape_or_pm():
    c=TrayCaptureRetry(QUALITY,after=100,defer_smd_to_close_view=True)
    for stamp in range(101,105):
        p=frame(stamp)
        for d in p['stable_detections']:
            if d['part_type']=='right_white_brown':d['median_detection_confidence']=.3
        result=c.observe(p,stamp+.1)
    assert result is not None
    c=TrayCaptureRetry(QUALITY,after=100,defer_smd_to_close_view=True)
    for stamp in range(101,105):
        p=frame(stamp);part(p,'long_orange',2)['median_detection_confidence']=.1
        part(p,'right_white_brown',3)['median_mask_shape_score']=.1
        assert c.observe(p,stamp+.1) is None
    assert ('long_orange',2) not in c.accepted
    assert ('right_white_brown',3) not in c.accepted

"""Exercise production detector methods without ROS, a model, or connected hardware."""
import ast
from collections import deque
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from segmentation_scale_retry import passes_quality, merge_scale_retry


def load_detector():
    path = SCRIPTS / 'detect_tray_parts.py'
    tree = ast.parse(path.read_text())
    definitions = [node for node in tree.body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    detector = next(node for node in definitions if isinstance(node, ast.ClassDef))
    detector.bases = [ast.Name(id='object', ctx=ast.Load())]
    module = ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[]))
    namespace = dict(np=np, cv2=cv2, time=time, json=json, Rotation=Rotation,
                     String=SimpleNamespace, COLORS={'hbm': (220, 0, 220)},
                     passes_quality=passes_quality, merge_scale_retry=merge_scale_retry)
    exec(compile(module, str(path), 'exec'), namespace)
    return namespace['Detector']


Detector = load_detector()


def header(stamp_ns):
    return SimpleNamespace(stamp=SimpleNamespace(
        sec=stamp_ns // 1_000_000_000, nanosec=stamp_ns % 1_000_000_000))


def depth_message(value=500, stamp_ns=1_000_000_000, shape=(80, 80)):
    data = np.full(shape, value, np.uint16)
    return SimpleNamespace(header=header(stamp_ns), encoding='16UC1',
                           height=shape[0], width=shape[1], step=shape[1] * 2,
                           data=data.tobytes())


def robot_message(pose=(100, 200, 300, 0, 0, 0)):
    names = ('flange_x_cur_pos', 'flange_y_cur_pos', 'flange_z_cur_pos',
             'flange_a_cur_pos', 'flange_b_cur_pos', 'flange_c_cur_pos')
    return SimpleNamespace(**dict(zip(names, pose)))


def prediction():
    points = np.float32([[10, 10], [30, 10], [30, 20], [10, 20]])
    return SimpleNamespace(
        masks=SimpleNamespace(xy=[points]),
        boxes=SimpleNamespace(conf=SimpleNamespace(cpu=lambda: np.array([.9])),
                              cls=SimpleNamespace(cpu=lambda: np.array([5]))))


@pytest.fixture
def detector(tmp_path):
    d = Detector.__new__(Detector)
    d.a = SimpleNamespace(
        process_hz=2., max_sync_ms=120., max_registration_age_ms=500.,
        robot_stable_samples=3, max_robot_state_age_sec=5., robot_stream_gap_sec=1.,
        max_robot_sample_jump_mm=10000., max_robot_sample_jump_deg=180.,
        max_robot_translation_span_mm=1., max_robot_rotation_span_deg=1.,
        history_pose_match_mm=1., history_pose_match_deg=1., min_stable_hits=1,
        track_radius_px=20., seg_crop_padding=0, seg_confidence=.2,
        power_seg_confidence=.2, seg_image_size=640, seg_device='cpu', seg_nms_iou=.5,
        capture_inductor_background=None, overlay_hold_frames=3,
        output_json=tmp_path / 'detections.json', handeye_file=tmp_path / 'handeye.json',
    )
    d.rw = d.rh = 80
    d.bins = [dict(part_spec_id='hbm', roi_px=[0, 0, 80, 80], expected_count=1,
                   display_name='HBM', section_polygon_normalized=[[0, 0], [1, 0], [1, 1], [0, 1]])]
    d.specs = {'hbm': {'nominal_size_mm': {'x': 20, 'y': 10}}}
    d.seg_class_ids = {'hbm': 5}
    d.seg_single_areas = {'hbm': 200.}
    d.seg_quality = {'hbm': dict(minimum_detection_confidence=.2,
                                minimum_mask_shape_score=.2, minimum_rectangularity=.2)}
    d.seg_model = SimpleNamespace(predict=lambda *args, **kwargs: [prediction()])
    d.inductor_background = None
    d.observation_lock = threading.RLock()
    d.snapshot_lock = threading.Lock()
    d.depth = d.info = d.robot = d.previous_robot_pose = None
    d.ds = 0
    d.robot_time = d.last = 0.
    d.pose_history = deque(maxlen=3)
    d.history = deque(maxlen=3)
    d.count_history = deque(maxlen=3)
    d.frame_index = d.overlay_frame = 0
    d.overlay_tracks, d.overlay_counts = {}, {}
    d.display_tracks, d.display_counts = {}, {}
    d.shared_homography = np.eye(3)
    d.shared_registration_stamp_ns = 1_000_000_000
    d.shared_registration_state = 'TRACKING'
    d.registration_generation = 0
    from tray_source_identity import TraySourceIdentity
    d.detector_session_id = 'test-detector-session'
    d.source_identity = TraySourceIdentity()
    d.registration_state = None
    d.get_logger = lambda: SimpleNamespace(info=lambda _: None)
    d.published = []
    d.overlay_state_pub = d.counts_pub = d.unity_state_pub = SimpleNamespace(publish=d.published.append)
    d.euler = 'xyz'
    d.T_flange_camera = np.eye(4)
    d.handeye_sha256 = 'fixture'
    d.depth_cb(depth_message())
    d.info_cb(SimpleNamespace(header=header(1_000_000_000),
                              k=[100., 0., 0., 0., 100., 0., 0., 0., 1.]))
    for _ in range(3):
        d.robot_cb(robot_message())
    return d


@pytest.mark.parametrize('pause_at', ['decode', 'prediction'])
def test_async_updates_preserve_entire_observation_xyz(detector, monkeypatch, pause_at):
    entered, resume = threading.Event(), threading.Event()

    def pause():
        entered.set()
        assert resume.wait(5), 'Timed out waiting for injected sensor callbacks'

    if pause_at == 'prediction':
        def delayed_predict(*args, **kwargs):
            pause()
            return [prediction()]
        detector.seg_model.predict = delayed_predict
    else:
        decode = cv2.imdecode

        def delayed_decode(*args, **kwargs):
            pause()
            return decode(*args, **kwargs)
        monkeypatch.setattr(cv2, 'imdecode', delayed_decode)
    ok, jpeg = cv2.imencode('.jpg', np.zeros((80, 80, 3), np.uint8))
    assert ok
    message = SimpleNamespace(header=header(1_000_000_000), data=jpeg.tobytes())
    errors = []

    def run():
        try:
            detector.process_color(message)
        except Exception as exc:
            errors.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        assert entered.wait(5), errors
        # A newer frame even changes dimensions: no downstream step may read it.
        detector.depth_cb(depth_message(900, 2_000_000_000, shape=(12, 12)))
        detector.info.k[0] = 300.
        detector.info_cb(SimpleNamespace(header=header(2_000_000_000), k=[300.] * 9))
        # Feedback jitter stays inside existing stability/matching limits, but
        # must still never replace the captured pose in the reported transform.
        detector.robot_cb(robot_message((100.5, 200.5, 300.5, 0, 0, .5)))
    finally:
        resume.set()
        worker.join(5)
    assert not worker.is_alive()
    assert not errors
    result = json.loads(detector.a.output_json.read_text())
    assert result['depth_timestamp_ros_ns'] == 1_000_000_000
    assert result['camera_info_timestamp_ros_ns'] == 1_000_000_000
    assert result['depth_sync_ms'] == 0.
    assert result['base_transform_status'] == 'VALID_COORDINATES_ONLY'
    assert result['detections'][0]['camera_xyz_m'] == pytest.approx([.1, .075, .5])
    assert result['stable_detections'][0]['camera_xyz_m'] == pytest.approx([.1, .075, .5])
    assert result['stable_detections'][0]['base_xyz_mm'] == pytest.approx([200., 275., 800.])
    assert result['flange_pose_mm_deg'] == [100., 200., 300., 0., 0., 0.]
    assert detector.history[-1][1][0]['_flange_pose'] == result['flange_pose_mm_deg']


@pytest.mark.parametrize('feedback, expected', [
    ('stable', 'VALID_COORDINATES_ONLY'),
    ('stale_at_capture', 'NO_FRESH_ROBOT_STATE'),
    ('stream_stopped', 'NO_FRESH_ROBOT_STATE'),
    ('moving', 'ROBOT_MOVING'),
    ('moved_and_settled', 'ROBOT_MOVING'),
])
def test_slow_inference_checks_capture_and_publication_feedback_separately(
        detector, monkeypatch, feedback, expected):
    clock = [10.]
    monkeypatch.setitem(detector.process_color.__func__.__globals__, 'time',
                        SimpleNamespace(monotonic=lambda: clock[0]))
    detector.a.max_robot_state_age_sec = 1.  # Production default, below inference duration.
    detector.robot_cb(robot_message())
    if feedback == 'stale_at_capture':
        detector.robot_time = 8.5

    def slow_predict(*args, **kwargs):
        # A 1.4-second prediction receives state updates throughout its execution.
        for step in range(1, 8):
            clock[0] = 10. + .2 * step
            if feedback != 'stream_stopped':
                if feedback == 'moved_and_settled' or (feedback == 'moving' and step == 7):
                    detector.robot_cb(robot_message((120, 200, 300, 0, 0, 0)))
                else:
                    detector.robot_cb(robot_message((100.5, 200.5, 300.5, 0, 0, .5)))
        detector.depth_cb(depth_message(900, 2_400_000_000))
        return [prediction()]

    detector.seg_model.predict = slow_predict
    ok, jpeg = cv2.imencode('.jpg', np.zeros((80, 80, 3), np.uint8))
    assert ok
    detector.process_color(SimpleNamespace(header=header(1_000_000_000), data=jpeg.tobytes()))
    result = json.loads(detector.a.output_json.read_text())
    assert result['base_transform_status'] == expected
    assert result['detections'][0]['camera_xyz_m'] == pytest.approx([.1, .075, .5])
    stable = result['stable_detections'][0]
    assert stable['camera_xyz_m'] == pytest.approx([.1, .075, .5])
    if expected == 'VALID_COORDINATES_ONLY':
        assert stable['base_xyz_mm'] == pytest.approx([200., 275., 800.])
        assert result['flange_pose_mm_deg'] == [100., 200., 300., 0., 0., 0.]
    else:
        assert 'base_xyz_mm' not in stable
    unity = json.loads(detector.published[-1].data)
    assert unity['valid'] is (expected == 'VALID_COORDINATES_ONLY')


@pytest.mark.parametrize('fallback', [False, True])
def test_segmented_median_uses_supplied_depth_including_fallback(detector, fallback):
    depth = np.full((80, 80), 500., np.float32)
    if fallback:
        # Only the dilated ring has valid depth; the eroded mask is invalid.
        depth[10:21, 10:31] = 0.
    detector.depth_cb(depth_message(900))
    image = np.zeros((80, 80, 3), np.uint8)
    found, _, _ = detector.find_segmented(
        detector.bins[0], image, image, depth, 100., 100., 0., 0., np.eye(3), prediction())
    assert len(found) == 1
    assert found[0]['camera_xyz_m'] == pytest.approx([.1, .075, .5])


def test_classic_detection_uses_supplied_depth(detector):
    detector.a.__dict__.update(
        min_height_mm=1., max_height_threshold_mm=20., vrm_max_value=50.,
        min_area_ratio=.1, max_area_ratio=2., min_area_score=.1,
        min_aspect_score=.1, min_rectangularity=.1)
    detector.specs['hbm']['nominal_size_mm'] = dict(x=100., y=100., height=10.)
    detector.depth_cb(depth_message(900, shape=(12, 12)))
    depth = np.full((80, 80), 500., np.float32)
    image = np.zeros((80, 80, 3), np.uint8)
    value = np.full((80, 80), 255, np.uint8)
    value[20:41, 20:41] = 0
    found, _, floor = detector.find(
        detector.bins[0], image, None, depth, value, value, value,
        100., 100., 0., 0., np.eye(3))
    assert floor == 500.
    assert len(found) == 1
    assert found[0]['camera_xyz_m'] == pytest.approx([.15, .15, .5])


@pytest.mark.parametrize('offset, accepted', [(120_000_000, True), (120_000_001, False),
                                            (-120_000_001, False)])
def test_snapshot_preserves_existing_sync_limit(detector, offset, accepted):
    observation = detector.capture_observation(SimpleNamespace(header=header(1_000_000_000 + offset)))
    assert (observation is not None) is accepted


def test_missing_depth_or_camera_info_skips_observation(detector):
    message = SimpleNamespace(header=header(1_000_000_000))
    saved = detector.depth
    detector.depth = None
    assert detector.capture_observation(message) is None
    detector.depth, detector.info = saved, None
    assert detector.capture_observation(message) is None


def test_captured_stale_pose_is_not_refreshed_by_newer_callback(detector):
    detector.robot_time = time.monotonic() - 10.
    observation = detector.capture_observation(SimpleNamespace(header=header(1_000_000_000)))
    detector.robot_cb(robot_message())
    result = {'stable_detections': [{'camera_xyz_m': [.1, .075, .5], 'angle_deg': 0.}]}
    assert detector.add_base_coordinates(result, 100., 100., observation) == 'NO_FRESH_ROBOT_STATE'
    assert 'base_xyz_mm' not in result['stable_detections'][0]


def test_depth_callback_owns_immutable_snapshot_data(detector):
    message = depth_message()
    message.data = bytearray(message.data)
    detector.depth_cb(message)
    observation = detector.capture_observation(SimpleNamespace(header=message.header))
    message.data[:] = bytes(len(message.data))
    assert np.all(observation['depth'] == 500)
    with pytest.raises(ValueError):
        observation['depth'][0, 0] = 900

"""Offline node tests: ROS, camera opening, subprocesses and HTTP are forbidden."""

import importlib.util
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import cv2
import numpy as np
import pytest


PROJECT = Path(__file__).resolve().parents[1]


@pytest.fixture
def camera_modules(monkeypatch):
    class Message:
        def __init__(self):
            self.header = SimpleNamespace()

    fake_modules = {
        "rclpy": dict(ok=lambda: True),
        "rclpy.node": dict(Node=object),
        "rclpy.executors": dict(ExternalShutdownException=RuntimeError),
        "rclpy.qos": dict(
            DurabilityPolicy=SimpleNamespace(VOLATILE=0),
            HistoryPolicy=SimpleNamespace(KEEP_LAST=0),
            QoSProfile=Mock(),
            ReliabilityPolicy=SimpleNamespace(BEST_EFFORT=0),
        ),
        "cv_bridge": dict(CvBridge=Mock()),
        "sensor_msgs": {},
        "sensor_msgs.msg": dict(CameraInfo=Message, CompressedImage=Message, Image=Message),
        "std_msgs": {},
        "std_msgs.msg": dict(Header=Message),
        "std_srvs": {},
        "std_srvs.srv": dict(Trigger=object),
    }
    for name, attrs in fake_modules.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)

    loaded = []
    for index, path in enumerate((
        PROJECT / "camera2_scrcpy/camera2_ros_node.py",
        PROJECT / "gopro_camera3/notebooks/gopro_camera3_node.py",
    )):
        spec = importlib.util.spec_from_file_location(f"offline_camera_{index}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        loaded.append(module)
    s22, gopro = loaded
    forbidden = Mock(side_effect=AssertionError("Live camera/ROS/process access forbidden"))
    monkeypatch.setattr(cv2, "VideoCapture", forbidden)
    monkeypatch.setattr(gopro.requests, "get", forbidden)
    monkeypatch.setattr(gopro.subprocess, "Popen", forbidden)
    monkeypatch.setattr(s22.rclpy, "init", forbidden, raising=False)
    return SimpleNamespace(s22=s22, gopro=gopro)


@pytest.fixture
def s22_node(camera_modules, monkeypatch, tmp_path):
    node = camera_modules.s22.Camera2Node.__new__(camera_modules.s22.Camera2Node)
    node.frame_lock = threading.Lock()
    node.frame_condition = threading.Condition(node.frame_lock)
    node.stop_capture = threading.Event()
    node.latest_frame = np.zeros((8, 12, 3), dtype=np.uint8)
    node.latest_capture_stamp = object()
    node.last_frame_at = 100.0
    node.latest_sequence = 1
    node.control_published_sequence = 0
    node.analysis_published_sequence = 0
    node.control_publish_count = 0
    node.analysis_publish_count = 0
    node.inspection_dir = tmp_path / "snapshots"
    node.frame_id = "camera2_optical_frame"
    node.get_clock = Mock()
    node.get_logger = Mock()
    node.inspection_pub = Mock()
    node.stream_pub = Mock()
    node.info_pub = Mock()
    node.compressed_pub = Mock()
    node.compressed_pub.get_subscription_count.return_value = 1
    node.publish_raw = False
    node.stream_width = node.output_width = 12
    node.stream_height = node.output_height = 8
    node.stream_jpeg_quality = 90
    node.jpeg_quality = 95
    monkeypatch.setattr(camera_modules.s22.time, "monotonic", lambda: 100.05)
    return node


@pytest.mark.parametrize("age", [0.201, 5.0, 100.0, -1.0])
def test_s22_snapshot_rejects_stale_or_invalid_age(s22_node, camera_modules, monkeypatch, age):
    monkeypatch.setattr(camera_modules.s22.time, "monotonic", lambda: 100.0 + age)
    result = s22_node.capture_inspection_frame(None, SimpleNamespace())
    assert result.success is False
    s22_node.inspection_pub.publish.assert_not_called()
    assert not s22_node.inspection_dir.exists()


@pytest.mark.parametrize("missing", ["frame", "stamp", "shutdown"])
def test_s22_snapshot_rejects_unavailable_capture(s22_node, missing):
    if missing == "frame":
        s22_node.latest_frame = None
    elif missing == "stamp":
        s22_node.latest_capture_stamp = None
    else:
        s22_node.stop_capture.set()
    result = s22_node.capture_inspection_frame(None, SimpleNamespace())
    assert result.success is False
    s22_node.inspection_pub.publish.assert_not_called()
    assert not s22_node.inspection_dir.exists()


def test_s22_fresh_snapshot_keeps_capture_stamp_and_lossless_pixels(s22_node):
    result = s22_node.capture_inspection_frame(None, SimpleNamespace())
    assert result.success is True
    message = s22_node.inspection_pub.publish.call_args.args[0]
    assert message.header.stamp is s22_node.latest_capture_stamp
    assert message.header.frame_id == "camera2_optical_frame"
    assert message.format == "png"
    saved = list(s22_node.inspection_dir.glob("*.png"))
    assert len(saved) == 1
    assert np.array_equal(cv2.imread(str(saved[0])), s22_node.latest_frame)
    s22_node.get_clock.assert_not_called()


@pytest.mark.parametrize("method,publisher", [
    ("publish_frame", "stream_pub"),
    ("publish_analysis_frame", "compressed_pub"),
])
def test_s22_latest_frame_only_and_no_duplicate_publish(s22_node, method, publisher):
    s22_node.latest_sequence = 25  # frames 1..24 were overwritten before this tick
    s22_node.latest_frame[:] = 73
    getattr(s22_node, method)()
    getattr(s22_node, method)()
    publish = getattr(s22_node, publisher).publish
    publish.assert_called_once()
    message = publish.call_args.args[0]
    assert message.header.stamp is s22_node.latest_capture_stamp
    decoded = cv2.imdecode(np.frombuffer(message.data, np.uint8), cv2.IMREAD_COLOR)
    assert np.all(decoded == 73)


@pytest.fixture
def gopro_node(camera_modules):
    node = camera_modules.gopro.GoProCamera3.__new__(camera_modules.gopro.GoProCamera3)
    node.running = True
    node.stop_event = threading.Event()
    node.pipeline_lock = threading.Lock()
    node.frame_lock = threading.Lock()
    node.decoder = None
    node.transport = "usb"
    node.webcam = Mock()
    node.port = 8554
    node.camera_resolution = 7
    node.stall_timeout = 0.1
    node.restart_count = 0
    node.get_logger = Mock()
    node._wireless_get = Mock()
    return node


@pytest.mark.parametrize("transport,stop_stage", [
    ("usb", "enable"), ("usb", "decoder"),
    ("wifi", "decoder"), ("wifi", "preview_stop"),
])
def test_gopro_shutdown_during_start_does_not_restart_camera(gopro_node, transport, stop_stage):
    node = gopro_node
    node.transport = transport

    def request_stop(*args, **kwargs):
        node.running = False
        node.stop_event.set()

    node._spawn_decoder = Mock()
    if stop_stage == "enable":
        node.webcam.enable.side_effect = request_stop
    elif stop_stage == "decoder":
        node._spawn_decoder.side_effect = request_stop
    else:
        node._wireless_get.side_effect = request_stop
    node._start_pipeline()
    node.webcam.start.assert_not_called()
    assert not any("stream/start" in call.args[0] for call in node._wireless_get.call_args_list)
    if stop_stage == "enable":
        node._spawn_decoder.assert_not_called()


def test_gopro_stop_reaps_decoder_and_closes_pipe(gopro_node):
    decoder = Mock()
    gopro_node.decoder = decoder
    gopro_node._stop_decoder()
    assert gopro_node.decoder is None
    decoder.terminate.assert_called_once()
    decoder.wait.assert_called_once_with(timeout=2.0)
    decoder.stdout.close.assert_called_once()
    gopro_node._stop_decoder()
    decoder.terminate.assert_called_once()


@pytest.mark.parametrize("error", [OSError("broken pipe"), ValueError("closed fd")])
def test_gopro_pipe_failure_enters_normal_recovery(gopro_node, camera_modules, monkeypatch, error):
    node = gopro_node
    node.frame_bytes = 6
    node.decoder = Mock()
    monkeypatch.setattr(camera_modules.gopro.select, "select", Mock(side_effect=error))
    assert node._read_frame_bytes() is None


def test_gopro_close_serializes_with_inflight_recovery(gopro_node):
    node = gopro_node
    stop_called = threading.Event()
    node._stop_decoder = Mock(side_effect=stop_called.set)
    node.pipeline_lock.acquire()
    thread = threading.Thread(target=node.close, daemon=True)
    thread.start()
    try:
        assert node.stop_event.wait(1.0), "close must request stop before taking the lock"
        assert not stop_called.is_set(), "decoder teardown must wait for recovery ownership"
    finally:
        node.pipeline_lock.release()
        thread.join(timeout=1.0)
    assert not thread.is_alive()
    node._stop_decoder.assert_called_once()
    node.webcam.disable.assert_called_once()


def test_gopro_retry_count_is_bounded(gopro_node):
    node = gopro_node
    node._spawn_decoder = Mock(side_effect=RuntimeError("synthetic decoder failure"))
    node._stop_decoder = Mock()
    node.stop_event = Mock()
    node.stop_event.wait.return_value = False
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        node._start_pipeline()
    assert node._spawn_decoder.call_count == 3
    assert node._stop_decoder.call_count == 3
    node.webcam.start.assert_not_called()


def test_gopro_retry_backoff_stops_on_shutdown(gopro_node):
    node = gopro_node
    node._spawn_decoder = Mock(side_effect=RuntimeError("synthetic decoder failure"))
    node._stop_decoder = Mock()

    def stop_during_backoff(timeout):
        node.running = False
        return True

    node.stop_event = Mock()
    node.stop_event.wait.side_effect = stop_during_backoff
    node._start_pipeline()
    assert node._spawn_decoder.call_count == 1
    node.stop_event.wait.assert_called_once_with(1.0)


def test_gopro_partial_reads_assemble_one_writable_frame(gopro_node, camera_modules, monkeypatch):
    node = gopro_node
    node.frame_bytes = 6
    node.decoder = Mock()
    node.decoder.stdout.fileno.return_value = 42
    monkeypatch.setattr(camera_modules.gopro.select, "select", Mock(
        return_value=([node.decoder.stdout], [], []),
    ))
    read = Mock(side_effect=[b"ab", b"c", b"def"])
    monkeypatch.setattr(camera_modules.gopro.os, "read", read)
    data = node._read_frame_bytes()
    assert isinstance(data, bytearray)
    assert data == b"abcdef"
    assert [call.args for call in read.call_args_list] == [(42, 6), (42, 4), (42, 3)]
    assert np.frombuffer(data, np.uint8).flags.writeable


def test_gopro_timeout_kills_and_closes_decoder_pipe(gopro_node, camera_modules):
    decoder = Mock()
    decoder.wait.side_effect = [camera_modules.gopro.subprocess.TimeoutExpired("ffmpeg", 2.0), 0]
    gopro_node.decoder = decoder
    gopro_node._stop_decoder()
    decoder.kill.assert_called_once()
    assert [call.kwargs for call in decoder.wait.call_args_list] == [{"timeout": 2.0}, {"timeout": 1.0}]
    decoder.stdout.close.assert_called_once()


def test_gopro_latest_frame_only_preserves_timestamp(gopro_node):
    node = gopro_node
    node.width, node.height = 320, 180
    node.latest_frame = np.zeros((180, 320, 3), dtype=np.uint8)
    node.latest_capture_stamp = object()
    node.latest_frame_id = 26
    node.published_frame_id = 0
    node.published_frames = 0
    node.jpeg_quality = 88
    node.compressed_publisher = Mock()
    node.raw_publisher = Mock()
    node.publish_frame()
    node.publish_frame()
    node.compressed_publisher.publish.assert_called_once()
    message = node.compressed_publisher.publish.call_args.args[0]
    assert message.header.stamp is node.latest_capture_stamp
    assert message.header.frame_id == "camera3_optical_frame"
    assert node.published_frame_id == 26
    assert node.published_frames == 1
    node.raw_publisher.publish.assert_not_called()

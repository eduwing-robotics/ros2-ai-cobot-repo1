"""Viewer frame conversion and diagnostics; never start ROS, cameras or GUI."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import cv2
import numpy as np
import pytest

path = Path(__file__).resolve().parents[1] / 'scripts/camera_viewer/view_camera.py'
spec = importlib.util.spec_from_file_location('remote_camera_view', path)
viewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(viewer)


@pytest.mark.parametrize('alias,topic', list(viewer.TOPICS.items()))
def test_explicit_compressed_topic_aliases(alias, topic):
    assert viewer.topic_name(alias) == topic
    assert viewer.topic_name(topic) == topic


@pytest.mark.parametrize('topic', ['camera', '/camera/image_raw', 'image compressed'])
def test_ambiguous_raw_inputs_rejected(topic):
    with pytest.raises(Exception):
        viewer.topic_name(topic)


def test_graph_discovery_does_not_claim_image_delivery():
    pub = NS(topic_type='sensor_msgs/msg/CompressedImage')
    assert viewer.diagnose([], 0, 0).startswith('NO_PUBLISHER')
    assert viewer.diagnose([NS(topic_type='sensor_msgs/msg/Image')], 0, 0).startswith('WRONG_TYPE')
    assert viewer.diagnose([pub], 0, 0).startswith('NO_FRAMES')
    assert viewer.diagnose([pub], 4, 0).startswith('DECODE_FAILED')
    assert viewer.diagnose([pub], 4, 3).startswith('OK')


@pytest.mark.parametrize('extension', ['.jpg', '.png'])
def test_decoded_image_has_correct_bgr8_wire_layout(extension):
    pixels = np.full((9, 13, 3), [7, 51, 182], dtype=np.uint8)
    ok, compressed = cv2.imencode(extension, pixels)
    assert ok
    message = NS(data=compressed.tobytes(), header=NS(frame_id='test_camera'))
    decoded = viewer.decode(message)
    raw = viewer.raw_image(message, decoded, NS)
    assert raw.header is message.header
    assert (raw.width, raw.height, raw.step, raw.encoding) == (13, 9, 39, 'bgr8')
    assert len(raw.data) == raw.height * raw.step
    np.testing.assert_array_equal(np.frombuffer(raw.data, dtype=np.uint8).reshape(9, 13, 3), decoded)


@pytest.mark.parametrize('blob', [b'', b'not jpeg', b'\xff\xd8\xff\xd9'])
def test_invalid_frame_does_not_make_ready(blob):
    assert viewer.decode(NS(data=blob)) is None

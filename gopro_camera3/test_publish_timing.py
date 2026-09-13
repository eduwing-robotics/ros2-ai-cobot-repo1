"""Exercise the real publish method without opening a camera or ROS node."""
from types import SimpleNamespace
import threading
from unittest.mock import Mock

import numpy as np

from gopro_camera3.notebooks import gopro_camera3_node as camera


def publisher():
    return SimpleNamespace(
        frame_lock=threading.Lock(), latest_frame=np.zeros((720, 1280, 3), np.uint8),
        latest_frame_id=1, published_frame_id=0,
        latest_capture_stamp=SimpleNamespace(sec=1, nanosec=0),
        latest_frame_time=0.0,
        width=1280, height=720, jpeg_quality=75, published_frames=0,
        compressed_publisher=Mock(), raw_publisher=Mock(),
        bridge=Mock(), next_raw_publish_at=0.0,
    )


def test_skipped_frame_numbers_still_deliver_raw_without_bursts(monkeypatch):
    node = publisher()
    node.raw_publisher.get_subscription_count.return_value = 1
    # All IDs miss the old modulo-6 condition; the clock must drive raw output.
    for frame_id, now in [(1, 0.0), (7, 0.1), (13, 1.0), (19, 1.1), (25, 4.0)]:
        node.latest_frame_id = frame_id
        node.latest_frame_time = now
        monkeypatch.setattr(camera.time, 'monotonic', lambda now=now: now)
        camera.GoProCamera3.publish_frame(node)
    assert node.raw_publisher.publish.call_count == 3
    assert node.compressed_publisher.publish.call_count == 5
    assert node.next_raw_publish_at == 5.0


def test_raw_waits_for_subscriber_and_does_not_repeat_stale_frame(monkeypatch):
    node = publisher()
    node.latest_frame_time = 10.0
    monkeypatch.setattr(camera.time, 'monotonic', lambda: 10.0)
    node.raw_publisher.get_subscription_count.return_value = 0
    camera.GoProCamera3.publish_frame(node)
    node.raw_publisher.publish.assert_not_called()
    node.raw_publisher.get_subscription_count.return_value = 1
    camera.GoProCamera3.publish_frame(node)
    node.raw_publisher.publish.assert_not_called()
    node.latest_frame_id = 2
    camera.GoProCamera3.publish_frame(node)
    node.raw_publisher.publish.assert_called_once()


def test_old_decoded_frame_is_not_published_after_pause(monkeypatch):
    node = publisher()
    node.raw_publisher.get_subscription_count.return_value = 0
    monkeypatch.setattr(camera.time, 'monotonic', lambda: 1.0)
    camera.GoProCamera3.publish_frame(node)
    node.compressed_publisher.publish.assert_not_called()
    node.raw_publisher.publish.assert_not_called()
    node.latest_frame_time = 1.0
    camera.GoProCamera3.publish_frame(node)
    node.compressed_publisher.publish.assert_called_once()


def test_decoder_buffer_bounds_keep_resolution_and_no_frame_rate_conversion():
    node = SimpleNamespace(port=8554, width=1280, height=720)
    args = camera.GoProCamera3._decoder_command(node)
    url = args[args.index('-i') + 1]
    assert 'fifo_size=2048' in url and 'buffer_size=262144' in url
    assert '-probesize' not in args and '-analyzeduration' not in args
    assert 'scale=1280:720:flags=fast_bilinear' in args
    assert args[args.index('-fps_mode') + 1] == 'passthrough'

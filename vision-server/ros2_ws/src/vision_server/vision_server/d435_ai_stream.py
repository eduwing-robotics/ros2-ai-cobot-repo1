"""Camera-host-only D435 stream for remote AI inference.

This node must run on the computer physically connected to the D435. It
subscribes to the local raw RGB image, selects only the newest frames at the
configured rate, and JPEG-encodes those frames once for the remote AI server.
"""

import threading
import time

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import CompressedImage, Image


CAMERA_QOS = QoSProfile(
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)


class D435AIStream(Node):
    def __init__(self) -> None:
        super().__init__('d435_ai_stream')
        cv2.setNumThreads(2)
        self.declare_parameter(
            'input_topic', '/camera/camera/color/image_raw'
        )
        self.declare_parameter(
            'output_topic', '/camera/camera/color/image_ai/compressed'
        )
        self.declare_parameter('max_fps', 15.0)
        # This stream is the high-quality remote preview/AI fallback. Exact
        # inspection must still use the local raw RGB image on the D435 host.
        self.declare_parameter('jpeg_quality', 92)

        self._input_topic = str(self.get_parameter('input_topic').value)
        self._output_topic = str(self.get_parameter('output_topic').value)
        self._max_fps = max(0.5, float(self.get_parameter('max_fps').value))
        self._jpeg_quality = int(
            np.clip(int(self.get_parameter('jpeg_quality').value), 50, 95)
        )
        self._frame_lock = threading.Lock()
        self._latest_message = None
        self._latest_frame_id = 0
        self._published_frame_id = 0
        self._running = True
        self._input_count = 0
        self._output_count = 0
        self._last_encode_ms = 0.0
        self._last_age_ms = 0.0
        self._last_jpeg_kib = 0.0
        self._report_at = time.monotonic()

        self._publisher = self.create_publisher(
            CompressedImage, self._output_topic, CAMERA_QOS
        )
        self._subscription = self.create_subscription(
            Image, self._input_topic, self._on_image, CAMERA_QOS
        )
        self._worker = threading.Thread(
            target=self._publish_loop,
            name='d435-ai-jpeg',
            daemon=True,
        )
        self._worker.start()
        self.create_timer(5.0, self._report)
        self.get_logger().info(
            f'D435 AI stream: {self._input_topic} -> {self._output_topic}, '
            f'{self._max_fps:g} FPS, JPEG {self._jpeg_quality}'
        )

    @staticmethod
    def _decode(message: Image):
        encoding = str(message.encoding).lower()
        if encoding not in ('bgr8', 'rgb8'):
            return None
        channels = 3
        row = np.frombuffer(message.data, dtype=np.uint8).reshape(
            int(message.height), int(message.step)
        )
        image = row[:, : int(message.width) * channels].reshape(
            int(message.height), int(message.width), channels
        )
        if encoding == 'rgb8':
            return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image

    def _on_image(self, message: Image) -> None:
        """Store only the newest local frame; never JPEG-encode in DDS callback."""
        self._input_count += 1
        with self._frame_lock:
            self._latest_message = message
            self._latest_frame_id += 1

    def _publish_loop(self) -> None:
        """Encode at a fixed cadence and discard any superseded raw frames."""
        period = 1.0 / self._max_fps
        next_publish_at = time.monotonic()
        while self._running:
            remaining = next_publish_at - time.monotonic()
            if remaining > 0.0:
                time.sleep(min(remaining, 0.02))
                continue
            if not rclpy.ok():
                break
            with self._frame_lock:
                message = self._latest_message
                frame_id = self._latest_frame_id
            if message is not None and frame_id != self._published_frame_id:
                self._published_frame_id = frame_id
                started_at = time.monotonic()
                try:
                    self._publish_message(message)
                except Exception as exc:
                    if self._running and rclpy.ok():
                        self.get_logger().error(
                            f'D435 JPEG publish failed: {exc}',
                            throttle_duration_sec=3.0,
                        )
                self._last_encode_ms = (time.monotonic() - started_at) * 1000.0
            next_publish_at += period
            now = time.monotonic()
            if next_publish_at < now - period:
                next_publish_at = now

    def _publish_message(self, message: Image) -> None:
        image = self._decode(message)
        if image is None:
            self.get_logger().warning(
                f'Unsupported D435 RGB encoding: {message.encoding}',
                throttle_duration_sec=5.0,
            )
            return
        success, encoded = cv2.imencode(
            '.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
        )
        if not success:
            return
        output = CompressedImage()
        output.header = message.header
        output.format = 'jpeg'
        output.data = encoded.tobytes()
        self._publisher.publish(output)
        self._output_count += 1
        self._last_jpeg_kib = len(output.data) / 1024.0
        stamp_ns = (
            int(message.header.stamp.sec) * 1_000_000_000
            + int(message.header.stamp.nanosec)
        )
        if stamp_ns > 0:
            self._last_age_ms = max(
                0.0,
                (self.get_clock().now().nanoseconds - stamp_ns) / 1_000_000.0,
            )

    def _report(self) -> None:
        now = time.monotonic()
        elapsed = max(1e-6, now - self._report_at)
        self.get_logger().info(
            f'D435 AI stream rates: input={self._input_count / elapsed:.1f} FPS, '
            f'output={self._output_count / elapsed:.1f} FPS, '
            f'encode={self._last_encode_ms:.1f} ms, '
            f'age={self._last_age_ms:.1f} ms, '
            f'jpeg={self._last_jpeg_kib:.0f} KiB'
        )
        self._input_count = 0
        self._output_count = 0
        self._report_at = now

    def close(self) -> None:
        self._running = False
        if hasattr(self, '_worker'):
            self._worker.join(timeout=2.0)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = D435AIStream()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

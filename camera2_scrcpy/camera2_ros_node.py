#!/usr/bin/env python3
import argparse
from pathlib import Path
import threading
import time

import cv2
import rclpy
from rclpy.executors import ExternalShutdownException
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import CameraInfo, CompressedImage, Image
from std_msgs.msg import Header
from std_srvs.srv import Trigger


class Camera2Node(Node):
    # Match the documented 0.20 s source-freshness requirement. This is an
    # overview snapshot guard, not an optical inspection/defect threshold.
    INSPECTION_MAX_FRAME_AGE_SEC = 0.20

    def __init__(
        self,
        device: str,
        fps: float,
        jpeg_quality: int,
        publish_raw: bool,
        expected_width: int,
        expected_height: int,
        output_width: int,
        output_height: int,
        stream_width: int,
        stream_height: int,
        stream_jpeg_quality: int,
        analysis_fps: float,
        inspection_dir: Path,
    ):
        super().__init__('camera2')
        # OpenCV otherwise starts one worker per logical CPU in both this node
        # and the conveyor detector. Limiting each process avoids periodic CPU
        # oversubscription and gives steadier frame delivery.
        cv2.setNumThreads(2)
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f'Cannot open S22 scrcpy V4L2 device: {device}')
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.bridge = CvBridge()
        self.device = device
        self.last_reopen_attempt = 0.0
        self.started_at = time.monotonic()
        self.last_frame_at = 0.0
        self.consecutive_failures = 0
        self.frame_lock = threading.Lock()
        self.frame_condition = threading.Condition(self.frame_lock)
        self.latest_frame = None
        self.latest_capture_stamp = None
        self.latest_sequence = 0
        self.control_published_sequence = 0
        self.analysis_published_sequence = 0
        self.stop_capture = threading.Event()
        self.jpeg_quality = jpeg_quality
        self.publish_raw = bool(publish_raw)
        self.expected_width = int(expected_width)
        self.expected_height = int(expected_height)
        self.output_width = int(output_width)
        self.output_height = int(output_height)
        self.stream_width = int(stream_width)
        self.stream_height = int(stream_height)
        self.stream_jpeg_quality = int(stream_jpeg_quality)
        self.inspection_dir = Path(inspection_dir).expanduser().resolve()
        self.reported_input_format = False
        self.capture_count = 0
        self.control_publish_count = 0
        self.analysis_publish_count = 0
        self.rate_report_at = time.monotonic()
        self.publish_period = 1.0 / float(fps)
        self.analysis_publish_period = 1.0 / float(analysis_fps)
        # Camera frames are only useful while they are current. A reliable
        # queue can replay old full-HD JPEGs after a slow subscriber catches
        # up, which looks like stutter and also delays the conveyor stop
        # decision. Keep only the newest frame instead.
        camera_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.raw_pub = (
            self.create_publisher(Image, '/camera2/image_raw', camera_qos)
            if self.publish_raw
            else None
        )
        self.compressed_pub = self.create_publisher(
            CompressedImage, '/camera2/image_raw/compressed', camera_qos
        )
        self.stream_pub = self.create_publisher(
            CompressedImage, '/camera2/image_stream/compressed', camera_qos
        )
        self.info_pub = self.create_publisher(
            CameraInfo, '/camera2/camera_info', camera_qos
        )
        self.inspection_pub = self.create_publisher(
            CompressedImage,
            '/camera2/inspection_frame/compressed',
            camera_qos,
        )
        self.inspection_service = self.create_service(
            Trigger,
            '/camera2/capture_inspection_frame',
            self.capture_inspection_frame,
        )
        self.watchdog_timer = self.create_timer(1.0, self.check_stream)
        self.rate_timer = self.create_timer(5.0, self.report_rates)
        self.frame_id = 'camera2_optical_frame'
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            name='camera2_latest_frame',
            daemon=True,
        )
        self.publish_thread = threading.Thread(
            target=self._publish_loop,
            name='camera2_control_publisher',
            daemon=True,
        )
        self.analysis_thread = threading.Thread(
            target=self._analysis_publish_loop,
            name='camera2_analysis_publisher',
            daemon=True,
        )
        self.capture_thread.start()
        self.publish_thread.start()
        self.analysis_thread.start()
        self.get_logger().info(
            f'Publishing S22 camera {device} on /camera2/image_raw/compressed '
            f'(raw={self.publish_raw}, output={self.output_width}x'
            f'{self.output_height}, fps={fps:g}, jpeg_quality={jpeg_quality})'
        )
        self.get_logger().info(
            'Control-priority live stream: /camera2/image_stream/compressed '
            f'({self.stream_width}x{self.stream_height}, '
            f'jpeg_quality={self.stream_jpeg_quality})'
        )
        self.get_logger().info(
            'Subscriber-isolated analysis stream: '
            f'/camera2/image_raw/compressed (max {analysis_fps:g} FPS)'
        )
        self.get_logger().info(
            'Overview snapshot service: '
            '/camera2/capture_inspection_frame'
        )

    def publish_frame(self):
        with self.frame_lock:
            if (
                self.latest_frame is None
                or self.latest_sequence == self.control_published_sequence
            ):
                return
            # The capture thread replaces latest_frame with a new ndarray and
            # never mutates an already stored frame, so retaining this
            # reference is safe and avoids a full 1920x1080 memory copy.
            source_frame = self.latest_frame
            capture_stamp = self.latest_capture_stamp
            self.control_published_sequence = self.latest_sequence

        header = Header()
        # Timestamp the actual V4L2 read, not the later JPEG completion. This
        # makes `ros2 topic delay` expose any internal processing latency.
        header.stamp = capture_stamp or self.get_clock().now().to_msg()
        header.frame_id = self.frame_id

        # This is the always-on live transport used by the stop detector and
        # remote rqt viewers. Keeping it at 720p avoids sending a 50-65 Mbit/s
        # full-HD JPEG stream to every DDS subscriber.
        stream_frame = source_frame
        if (
            stream_frame.shape[1] != self.stream_width
            or stream_frame.shape[0] != self.stream_height
        ):
            stream_frame = cv2.resize(
                stream_frame,
                (self.stream_width, self.stream_height),
                interpolation=cv2.INTER_AREA,
            )
        encoded_ok, jpeg = cv2.imencode(
            '.jpg',
            stream_frame,
            [cv2.IMWRITE_JPEG_QUALITY, self.stream_jpeg_quality],
        )
        if encoded_ok:
            stream = CompressedImage()
            stream.header = header
            stream.format = 'jpeg'
            stream.data = jpeg.tobytes()
            self.stream_pub.publish(stream)
            self.control_publish_count += 1

        info = CameraInfo()
        info.header = header
        info.width = self.output_width
        info.height = self.output_height
        info.distortion_model = 'plumb_bob'
        self.info_pub.publish(info)

    def publish_analysis_frame(self):
        """Publish optional Full-HD output without delaying stop control."""
        wants_compressed = self.compressed_pub.get_subscription_count() > 0
        if not self.publish_raw and not wants_compressed:
            return

        with self.frame_lock:
            if (
                self.latest_frame is None
                or self.latest_sequence == self.analysis_published_sequence
            ):
                return
            source_frame = self.latest_frame
            capture_stamp = self.latest_capture_stamp
            self.analysis_published_sequence = self.latest_sequence

        header = Header()
        header.stamp = capture_stamp or self.get_clock().now().to_msg()
        header.frame_id = self.frame_id
        frame = source_frame
        if (
            frame.shape[1] != self.output_width
            or frame.shape[0] != self.output_height
        ):
            frame = cv2.resize(
                frame,
                (self.output_width, self.output_height),
                interpolation=cv2.INTER_AREA,
            )

        published = False
        if self.publish_raw:
            raw = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            raw.header = header
            self.raw_pub.publish(raw)
            published = True
        if wants_compressed:
            encoded_ok, jpeg = cv2.imencode(
                '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
            )
            if encoded_ok:
                compressed = CompressedImage()
                compressed.header = header
                compressed.format = 'jpeg'
                compressed.data = jpeg.tobytes()
                self.compressed_pub.publish(compressed)
                published = True
        if published:
            self.analysis_publish_count += 1

    def capture_inspection_frame(self, _request, response):
        with self.frame_lock:
            if (
                self.latest_frame is None
                or self.latest_capture_stamp is None
                or self.stop_capture.is_set()
                or not rclpy.ok()
            ):
                response.success = False
                response.message = 'No current S22 frame is available'
                return response
            frame_age = time.monotonic() - self.last_frame_at
            if not 0.0 <= frame_age <= self.INSPECTION_MAX_FRAME_AGE_SEC:
                response.success = False
                response.message = (
                    f'S22 frame is stale or has invalid age ({frame_age:.3f} s); '
                    'wait for the overview stream to recover'
                )
                return response
            # Capture thread replaces this ndarray and never mutates it.
            frame = self.latest_frame
            capture_stamp = self.latest_capture_stamp

        self.inspection_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        output_path = self.inspection_dir / (
            f's22_inspection_{timestamp}_{time.time_ns() % 1_000_000_000:09d}.png'
        )
        encoded_ok, png = cv2.imencode(
            '.png', frame, [cv2.IMWRITE_PNG_COMPRESSION, 3]
        )
        if not encoded_ok:
            response.success = False
            response.message = 'OpenCV could not encode the S22 frame as PNG'
            return response

        output_path.write_bytes(png.tobytes())
        header = Header()
        header.stamp = capture_stamp
        header.frame_id = self.frame_id
        inspection = CompressedImage()
        inspection.header = header
        inspection.format = 'png'
        inspection.data = png.tobytes()
        self.inspection_pub.publish(inspection)

        height, width = frame.shape[:2]
        response.success = True
        response.message = f'{output_path} ({width}x{height}, lossless PNG)'
        self.get_logger().info(f'Saved inspection frame: {response.message}')
        return response

    def _capture_loop(self):
        while not self.stop_capture.is_set():
            ok, frame = self.cap.read()
            if not ok:
                self.consecutive_failures += 1
                self.get_logger().warning(
                    'S22 scrcpy frame read failed',
                    throttle_duration_sec=3.0,
                )
                if self.consecutive_failures >= 10:
                    self._reopen_device()
                self.stop_capture.wait(0.01)
                continue

            captured_at = time.monotonic()
            capture_stamp = self.get_clock().now().to_msg()
            self.consecutive_failures = 0
            self.capture_count += 1
            if not self.reported_input_format:
                height, width = frame.shape[:2]
                self.get_logger().info(
                    f'S22 actual input: {width}x{height}'
                )
                if (
                    width != self.expected_width
                    or height != self.expected_height
                ):
                    self.get_logger().warning(
                        'S22 input does not match the requested '
                        f'{self.expected_width}x{self.expected_height}; '
                        'raising ROS JPEG quality cannot restore missing detail'
                    )
                self.reported_input_format = True
            with self.frame_condition:
                self.latest_frame = frame
                self.latest_capture_stamp = capture_stamp
                self.last_frame_at = captured_at
                self.latest_sequence += 1
                self.frame_condition.notify_all()

    def _publish_loop(self):
        """Publish immediately when a fresh source frame becomes available."""
        next_publish_at = 0.0
        while not self.stop_capture.is_set():
            with self.frame_condition:
                while not self.stop_capture.is_set() and rclpy.ok():
                    now = time.monotonic()
                    has_new_frame = (
                        self.latest_frame is not None
                        and self.latest_sequence
                        != self.control_published_sequence
                    )
                    if has_new_frame and now >= next_publish_at:
                        break
                    timeout = 0.5
                    if has_new_frame:
                        timeout = max(0.001, next_publish_at - now)
                    self.frame_condition.wait(timeout=timeout)
                if self.stop_capture.is_set() or not rclpy.ok():
                    break

            publish_started_at = time.monotonic()
            try:
                self.publish_frame()
            except Exception:
                # Ctrl+C may invalidate the ROS context just before the worker
                # observes stop_capture.
                if self.stop_capture.is_set() or not rclpy.ok():
                    break
                raise
            next_publish_at = publish_started_at + self.publish_period

    def _analysis_publish_loop(self):
        """Encode the optional analysis topic on a separate, capped cadence."""
        next_publish_at = time.monotonic()
        while not self.stop_capture.is_set():
            remaining = next_publish_at - time.monotonic()
            if remaining > 0.0 and self.stop_capture.wait(remaining):
                break
            if not rclpy.ok():
                break
            try:
                self.publish_analysis_frame()
            except Exception:
                if self.stop_capture.is_set() or not rclpy.ok():
                    break
                raise

            next_publish_at += self.analysis_publish_period
            now = time.monotonic()
            if next_publish_at < now - self.analysis_publish_period:
                next_publish_at = now

    def _reopen_device(self):
        now = time.monotonic()
        if now - self.last_reopen_attempt < 2.0:
            return
        self.last_reopen_attempt = now
        self.cap.release()
        self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.get_logger().info(
                f'Reopened S22 scrcpy V4L2 device: {self.device}'
            )
            self.consecutive_failures = 0

    def check_stream(self):
        now = time.monotonic()
        if self.last_frame_at == 0.0:
            elapsed = now - self.started_at
            if elapsed < 8.0:
                return
            self.get_logger().error(
                f'No video frame received from {self.device} for {elapsed:.1f} s; '
                'requesting scrcpy reconnect'
            )
        elif now - self.last_frame_at < 5.0:
            return
        else:
            self.get_logger().error(
                f'Video stream stalled for {now - self.last_frame_at:.1f} s; '
                'requesting scrcpy reconnect'
            )
        if rclpy.ok():
            rclpy.shutdown()

    def report_rates(self):
        now = time.monotonic()
        elapsed = max(1e-6, now - self.rate_report_at)
        self.get_logger().info(
            f'S22 rates: capture={self.capture_count / elapsed:.1f} FPS, '
            f'control={self.control_publish_count / elapsed:.1f} FPS, '
            f'analysis={self.analysis_publish_count / elapsed:.1f} FPS'
        )
        self.capture_count = 0
        self.control_publish_count = 0
        self.analysis_publish_count = 0
        self.rate_report_at = now

    def destroy_node(self):
        self.stop_capture.set()
        with self.frame_condition:
            self.frame_condition.notify_all()
        if self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        if self.publish_thread.is_alive():
            self.publish_thread.join(timeout=2.0)
        if self.analysis_thread.is_alive():
            self.analysis_thread.join(timeout=2.0)
        self.cap.release()
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', default='/dev/video10')
    parser.add_argument('--fps', type=float, default=15.0)
    parser.add_argument('--jpeg-quality', type=int, default=95)
    parser.add_argument('--expected-width', type=int, default=1920)
    parser.add_argument('--expected-height', type=int, default=1080)
    parser.add_argument('--output-width', type=int, default=1920)
    parser.add_argument('--output-height', type=int, default=1080)
    parser.add_argument('--stream-width', type=int, default=1280)
    parser.add_argument('--stream-height', type=int, default=720)
    parser.add_argument('--stream-jpeg-quality', type=int, default=88)
    parser.add_argument('--analysis-fps', type=float, default=5.0)
    parser.add_argument(
        '--inspection-dir',
        type=Path,
        default=Path.home() / 'KSMC/runtime/inspection',
    )
    parser.add_argument(
        '--publish-raw',
        action='store_true',
        help='Also publish the high-bandwidth /camera2/image_raw topic',
    )
    args = parser.parse_args()
    if not 1.0 <= args.fps <= 60.0:
        parser.error('--fps must be between 1 and 60')
    if not 0.5 <= args.analysis_fps <= 30.0:
        parser.error('--analysis-fps must be between 0.5 and 30')
    if not 70 <= args.jpeg_quality <= 100:
        parser.error('--jpeg-quality must be between 70 and 100')
    if (
        args.expected_width <= 0
        or args.expected_height <= 0
        or args.output_width <= 0
        or args.output_height <= 0
        or args.stream_width <= 0
        or args.stream_height <= 0
    ):
        parser.error('expected image dimensions must be positive')
    if not 70 <= args.stream_jpeg_quality <= 100:
        parser.error('--stream-jpeg-quality must be between 70 and 100')

    rclpy.init()
    node = Camera2Node(
        args.device,
        args.fps,
        args.jpeg_quality,
        args.publish_raw,
        args.expected_width,
        args.expected_height,
        args.output_width,
        args.output_height,
        args.stream_width,
        args.stream_height,
        args.stream_jpeg_quality,
        args.analysis_fps,
        args.inspection_dir,
    )
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except Exception:
        # The stream watchdog intentionally shuts down the context so the
        # outer scrcpy launcher can reconnect. Jazzy may surface that normal
        # shutdown as RCLError while an executor is waiting.
        if rclpy.ok():
            raise
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

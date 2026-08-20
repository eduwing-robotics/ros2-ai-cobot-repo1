#!/usr/bin/env python3
import argparse
import threading
import time

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, CompressedImage, Image


class Camera2Node(Node):
    def __init__(self, device: str, fps: float, jpeg_quality: int):
        super().__init__('camera2')
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError(f'Cannot open DroidCam device: {device}')
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.bridge = CvBridge()
        self.device = device
        self.last_reopen_attempt = 0.0
        self.consecutive_failures = 0
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.latest_sequence = 0
        self.published_sequence = 0
        self.stop_capture = threading.Event()
        self.jpeg_quality = jpeg_quality
        self.raw_pub = self.create_publisher(Image, '/camera2/image_raw', 2)
        self.compressed_pub = self.create_publisher(
            CompressedImage, '/camera2/image_raw/compressed', 2
        )
        self.info_pub = self.create_publisher(CameraInfo, '/camera2/camera_info', 2)
        self.timer = self.create_timer(1.0 / fps, self.publish_frame)
        self.frame_id = 'camera2_optical_frame'
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            name='camera2_latest_frame',
            daemon=True,
        )
        self.capture_thread.start()
        self.get_logger().info(
            f'Publishing DroidCam {device} on /camera2/image_raw and '
            '/camera2/image_raw/compressed'
        )

    def publish_frame(self):
        with self.frame_lock:
            if self.latest_frame is None or self.latest_sequence == self.published_sequence:
                return
            frame = self.latest_frame.copy()
            self.published_sequence = self.latest_sequence

        stamp = self.get_clock().now().to_msg()
        raw = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        raw.header.stamp = stamp
        raw.header.frame_id = self.frame_id
        self.raw_pub.publish(raw)

        encoded_ok, jpeg = cv2.imencode(
            '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if encoded_ok:
            compressed = CompressedImage()
            compressed.header = raw.header
            compressed.format = 'jpeg'
            compressed.data = jpeg.tobytes()
            self.compressed_pub.publish(compressed)

        height, width = frame.shape[:2]
        info = CameraInfo()
        info.header = raw.header
        info.width = width
        info.height = height
        info.distortion_model = 'plumb_bob'
        self.info_pub.publish(info)

    def _capture_loop(self):
        while not self.stop_capture.is_set():
            ok, frame = self.cap.read()
            if not ok:
                self.consecutive_failures += 1
                self.get_logger().warning(
                    'DroidCam frame read failed',
                    throttle_duration_sec=3.0,
                )
                if self.consecutive_failures >= 10:
                    self._reopen_device()
                self.stop_capture.wait(0.01)
                continue

            self.consecutive_failures = 0
            with self.frame_lock:
                self.latest_frame = frame
                self.latest_sequence += 1

    def _reopen_device(self):
        now = time.monotonic()
        if now - self.last_reopen_attempt < 2.0:
            return
        self.last_reopen_attempt = now
        self.cap.release()
        self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.get_logger().info(f'Reopened DroidCam device: {self.device}')
            self.consecutive_failures = 0

    def destroy_node(self):
        self.stop_capture.set()
        if self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        self.cap.release()
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', default='/dev/video10')
    parser.add_argument('--fps', type=float, default=30.0)
    parser.add_argument('--jpeg-quality', type=int, default=95)
    args = parser.parse_args()

    rclpy.init()
    node = Camera2Node(args.device, args.fps, args.jpeg_quality)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

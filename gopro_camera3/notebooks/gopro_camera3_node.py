#!/usr/bin/env python3
"""Publish a HERO11 USB webcam stream as /camera3/image_raw.

The HERO11 uses a USB network connection for Webcam mode.  OpenGoPro starts
the stream and OpenCV receives the resulting UDP video; this is not a V4L2
device, so v4l2_camera is not involved in this path.
"""

import argparse
import os
import sys
import subprocess
import threading

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image


class GoProCamera3(Node):
    def __init__(self, serial: str, port: int):
        super().__init__("gopro_camera3")
        camera_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.raw_publisher = self.create_publisher(
            Image, "/camera3/image_raw", camera_qos
        )
        self.compressed_publisher = self.create_publisher(
            CompressedImage,
            "/camera3/image_raw/compressed",
            camera_qos,
        )
        self.bridge = CvBridge()
        self.port = port
        self.stream_url = f"udp://0.0.0.0:{port}"

        # Keep the vendored OpenGoPro demo usable without a pip build step.
        repo = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "third_party",
            "open_gopro_multi_webcam",
        )
        sys.path.insert(0, repo)
        from multi_webcam.webcam import Webcam

        self.webcam = Webcam(serial)
        self.webcam.start(port=port, resolution=12, fov=0)
        self.width = 1280
        self.height = 720
        self.frame_bytes = self.width * self.height * 3
        self.decoder = subprocess.Popen(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-f",
                "mpegts",
                "-i",
                f"udp://0.0.0.0:{port}?fifo_size=2000000&overrun_nonfatal=1&buffer_size=1048576",
                "-map",
                "0:v:0",
                "-an",
                "-vf",
                f"scale={self.width}:{self.height}:flags=fast_bilinear",
                "-pix_fmt",
                "bgr24",
                "-fps_mode",
                "passthrough",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=None,
            bufsize=0,
        )
        if self.decoder.stdout is None:
            self.webcam.disable()
            self.decoder.terminate()
            raise RuntimeError("FFmpeg decoder could not be opened")
        self.running = True
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.latest_frame_id = 0
        self.published_frame_id = 0
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.reader_thread.start()
        self.timer = self.create_timer(1.0 / 30.0, self.publish_frame)
        self.get_logger().info("Publishing GoPro HERO11 on /camera3/image_raw")

    def _read_loop(self):
        while self.running:
            data = bytearray()
            while self.running and len(data) < self.frame_bytes:
                chunk = self.decoder.stdout.read(self.frame_bytes - len(data))
                if not chunk:
                    if self.decoder.poll() is not None:
                        self.get_logger().error(
                            f"FFmpeg decoder stopped (exit={self.decoder.returncode})"
                        )
                        return
                    continue
                data.extend(chunk)
            if len(data) != self.frame_bytes:
                continue
            frame = np.frombuffer(bytes(data), dtype=np.uint8).reshape(
                (self.height, self.width, 3)
            )
            with self.frame_lock:
                self.latest_frame = frame.copy()
                self.latest_frame_id += 1

    def publish_frame(self):
        with self.frame_lock:
            frame = self.latest_frame
            frame_id = self.latest_frame_id
        if frame is None or frame_id == self.published_frame_id:
            return
        self.published_frame_id = frame_id

        stamp = self.get_clock().now().to_msg()
        ok, encoded = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
        )
        if ok:
            compressed = CompressedImage()
            compressed.header.stamp = stamp
            compressed.header.frame_id = "camera3_optical_frame"
            compressed.format = "jpeg"
            compressed.data = encoded.tobytes()
            self.compressed_publisher.publish(compressed)

        # Keep a low-rate raw topic for tools that cannot consume compressed
        # images, without forcing DDS to move ~83 MB/s continuously.
        if frame_id % 6 == 0 and self.raw_publisher.get_subscription_count() > 0:
            raw = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            raw.header.stamp = stamp
            raw.header.frame_id = "camera3_optical_frame"
            self.raw_publisher.publish(raw)

    def close(self):
        self.running = False
        if hasattr(self, "decoder"):
            self.decoder.terminate()
            try:
                self.decoder.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.decoder.kill()
        if hasattr(self, "reader_thread"):
            self.reader_thread.join(timeout=1.0)
        if hasattr(self, "webcam"):
            self.webcam.disable()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("serial", help="Last three characters of the GoPro serial number")
    parser.add_argument("--port", type=int, default=8554)
    args = parser.parse_args()

    rclpy.init()
    node = None
    try:
        node = GoProCamera3(args.serial, args.port)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

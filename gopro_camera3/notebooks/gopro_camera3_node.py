#!/usr/bin/env python3
"""Publish a HERO11 USB or Wi-Fi stream as /camera3/image_raw.

The HERO11 uses a USB network connection for Webcam mode.  OpenGoPro starts
the USB stream. Wi-Fi preview mode is started through the camera HTTP API.
FFmpeg receives the resulting UDP video in both modes.
"""

import argparse
from datetime import datetime
import os
import select
import sys
import subprocess
import threading
import time

import cv2
import numpy as np
import rclpy
import requests
from cv_bridge import CvBridge
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage, Image


class GoProCamera3(Node):
    def __init__(
        self,
        serial: str,
        port: int,
        camera_resolution: int,
        stall_timeout: float,
        transport: str,
        host: str,
        publish_fps: float,
        jpeg_quality: int,
    ):
        super().__init__("gopro_camera3")
        # Keep OpenCV from creating one worker per logical CPU. FFmpeg already
        # decodes/scales in a separate process, so a small fixed pool gives
        # steadier JPEG latency when other vision nodes are active.
        cv2.setNumThreads(2)
        # Keep only the newest sample on both paths. The compressed publisher
        # uses the sensor-data profile used by rqt_image_view and the existing
        # ROS-TCP Endpoint; depth one prevents a slow viewer from building a
        # stale JPEG queue.
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
        self.serial = serial
        self.port = port
        self.camera_resolution = camera_resolution
        self.stall_timeout = stall_timeout
        self.transport = transport
        self.host = host

        self.webcam = None
        if self.transport == "usb":
            # Keep the vendored OpenGoPro demo usable without a pip build step.
            repo = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "third_party",
                "open_gopro_multi_webcam",
            )
            sys.path.insert(0, repo)
            from multi_webcam.webcam import Webcam

            self.webcam = Webcam(serial)
        self.width = 1280
        self.height = 720
        self.frame_bytes = self.width * self.height * 3
        self.running = True
        self.stop_event = threading.Event()
        self.decoder = None
        self.pipeline_lock = threading.Lock()
        self.frame_lock = threading.Lock()
        self.latest_frame = None
        self.latest_capture_stamp = None
        self.latest_frame_id = 0
        self.published_frame_id = 0
        self.received_frames = 0
        self.published_frames = 0
        self.restart_count = 0
        self.publish_period = 1.0 / float(publish_fps)
        self.jpeg_quality = int(jpeg_quality)
        self._start_pipeline()
        # Do not include camera/decoder startup time in the first FPS sample.
        self.last_stats_time = time.monotonic()
        self.last_stats_received = 0
        self.last_stats_published = 0
        self.reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.publisher_thread = threading.Thread(
            target=self._publish_loop, daemon=True
        )
        self.reader_thread.start()
        self.publisher_thread.start()
        self.stats_timer = self.create_timer(5.0, self.report_stats)
        if self.transport == "wifi":
            self.keep_alive_timer = self.create_timer(
                2.5, self._wireless_keep_alive
            )
        self.get_logger().info(
            f"Publishing GoPro HERO11 {self.transport.upper()} stream at 1280x720; "
            f"latest-frame ROS output={publish_fps:g} FPS; "
            f"JPEG quality={self.jpeg_quality}; "
            "automatic stall recovery is enabled"
        )

    def _wireless_get(self, path: str):
        response = requests.get(
            f"http://{self.host}:8080/{path}", timeout=(1.0, 2.0)
        )
        response.raise_for_status()
        return response

    def _wireless_keep_alive(self):
        if not self.running:
            return
        try:
            self._wireless_get("gopro/camera/keep_alive")
        except requests.RequestException as exc:
            self.get_logger().warning(f"GoPro Wi-Fi keep-alive failed: {exc}")

    def _decoder_command(self):
        udp_url = (
            f"udp://0.0.0.0:{self.port}"
            "?fifo_size=2000000&overrun_nonfatal=1&buffer_size=1048576"
        )
        return [
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
            udp_url,
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
        ]

    def _spawn_decoder(self):
        if not self.running:
            return
        decoder = subprocess.Popen(
            self._decoder_command(),
            stdout=subprocess.PIPE,
            stderr=None,
            bufsize=0,
        )
        self.decoder = decoder
        if decoder.stdout is None:
            self._stop_decoder()
            raise RuntimeError("FFmpeg decoder could not be opened")
        # Address conflicts and invalid options terminate FFmpeg immediately.
        # Detect that here instead of entering a rapid recovery loop.
        self.stop_event.wait(0.2)
        if not self.running or self.decoder is not decoder:
            return
        if decoder.poll() is not None:
            return_code = decoder.returncode
            self._stop_decoder()
            raise RuntimeError(
                f"FFmpeg decoder exited during startup (code {return_code})"
            )

    def _stop_decoder(self):
        decoder = self.decoder
        self.decoder = None
        if decoder is None:
            return
        try:
            decoder.terminate()
            try:
                decoder.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                decoder.kill()
                decoder.wait(timeout=1.0)
        finally:
            if decoder.stdout is not None:
                decoder.stdout.close()

    def _start_pipeline(self):
        last_error = None
        for attempt in range(1, 4):
            if not self.running:
                return
            try:
                # Bind the UDP receiver before starting the camera so the
                # decoder receives the initial SPS/PPS and first keyframe.
                if self.transport == "usb":
                    assert self.webcam is not None
                    self.webcam.enable()
                    if not self.running:
                        return
                    self._spawn_decoder()
                    if not self.running:
                        return
                    self.webcam.start(
                        port=self.port,
                        resolution=self.camera_resolution,
                        fov=0,
                    )
                else:
                    self._spawn_decoder()
                    if not self.running:
                        return
                    # Stop any preview previously owned by Quik before making
                    # this computer the UDP destination.
                    self._wireless_get("gopro/camera/stream/stop")
                    if not self.running:
                        return
                    self._wireless_get(
                        f"gopro/camera/stream/start?port={self.port}"
                    )
                return
            except Exception as exc:  # camera/network errors are recoverable
                last_error = exc
                self._stop_decoder()
                self.get_logger().warning(
                    f"GoPro pipeline start failed ({attempt}/3): {exc}"
                )
                if attempt < 3 and self.running:
                    if self.stop_event.wait(float(attempt)):
                        return
        if not self.running:
            return
        raise RuntimeError(f"GoPro pipeline failed after 3 attempts: {last_error}")

    def _read_frame_bytes(self):
        decoder = self.decoder
        if decoder is None or decoder.stdout is None:
            return None
        data = bytearray()
        deadline = time.monotonic() + self.stall_timeout
        while self.running and len(data) < self.frame_bytes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                ready, _, _ = select.select(
                    [decoder.stdout], [], [], min(1.0, remaining)
                )
                if not ready:
                    if decoder.poll() is not None:
                        return None
                    continue
                chunk = os.read(
                    decoder.stdout.fileno(), self.frame_bytes - len(data)
                )
            except (OSError, ValueError):
                # close() can retire this pipe while select/read is waiting.
                # Treat broken/closed pipes like EOF so an active reader can
                # recover, and a stopping reader exits without a traceback.
                return None
            if not chunk:
                return None
            data.extend(chunk)
        # bytearray keeps the NumPy frame writable and avoids another 2.7 MB
        # copy for every 720p frame.
        return data if len(data) == self.frame_bytes else None

    def _recover_pipeline(self):
        with self.pipeline_lock:
            if not self.running:
                return
            self.restart_count += 1
            self.get_logger().warning(
                f"No complete frame for {self.stall_timeout:.1f}s; "
                f"restarting GoPro stream (restart #{self.restart_count})"
            )
            self._stop_decoder()
            if self.transport == "usb":
                assert self.webcam is not None
                try:
                    self.webcam.stop()
                except Exception:
                    pass
                try:
                    self.webcam.disable()
                except Exception:
                    pass
            else:
                try:
                    self._wireless_get("gopro/camera/stream/stop")
                except requests.RequestException:
                    pass
            if self.running:
                self._start_pipeline()

    def _read_loop(self):
        while self.running:
            data = self._read_frame_bytes()
            if data is None:
                if self.running:
                    try:
                        self._recover_pipeline()
                    except Exception as exc:
                        self.get_logger().error(f"GoPro recovery failed: {exc}")
                        self.stop_event.wait(2.0)
                    else:
                        # Do not hammer the camera/API if FFmpeg exits again
                        # before the first complete frame arrives.
                        self.stop_event.wait(0.5)
                continue
            frame = np.frombuffer(data, dtype=np.uint8).reshape(
                (self.height, self.width, 3)
            )
            with self.frame_lock:
                self.latest_frame = frame
                self.latest_capture_stamp = self.get_clock().now().to_msg()
                self.latest_frame_id += 1
                self.received_frames += 1

    def _publish_loop(self):
        """Publish the newest decoded frame and discard missed periods."""
        next_publish_at = time.monotonic()
        while self.running:
            remaining = next_publish_at - time.monotonic()
            if remaining > 0.0:
                self.stop_event.wait(min(remaining, 0.02))
                continue
            if not rclpy.ok():
                break
            try:
                self.publish_frame()
            except Exception as exc:
                if not self.running or not rclpy.ok():
                    break
                self.get_logger().error(
                    f"GoPro frame publish failed: {exc}",
                    throttle_duration_sec=3.0,
                )
            next_publish_at += self.publish_period
            now = time.monotonic()
            if next_publish_at < now - self.publish_period:
                next_publish_at = now

    def publish_frame(self):
        with self.frame_lock:
            frame = self.latest_frame
            frame_id = self.latest_frame_id
            capture_stamp = self.latest_capture_stamp
        if frame is None or frame_id == self.published_frame_id:
            return
        self.published_frame_id = frame_id

        # The decoder created this frame from a fresh writable bytearray and
        # replaces latest_frame on the next iteration. Draw in-place to avoid
        # a second full-frame copy; both ROS topics show the same clock.
        clock_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.55
        thickness = 1
        (text_width, text_height), baseline = cv2.getTextSize(
            clock_text, font, font_scale, thickness
        )
        margin = 12
        padding = 6
        text_x = self.width - margin - text_width
        text_y = self.height - margin - baseline
        cv2.rectangle(
            frame,
            (text_x - padding, text_y - text_height - padding),
            (text_x + text_width + padding, text_y + baseline + padding),
            (0, 0, 0),
            cv2.FILLED,
        )
        cv2.putText(
            frame,
            clock_text,
            (text_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

        stamp = capture_stamp or self.get_clock().now().to_msg()
        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
        )
        if ok:
            compressed = CompressedImage()
            compressed.header.stamp = stamp
            compressed.header.frame_id = "camera3_optical_frame"
            compressed.format = "jpeg"
            compressed.data = encoded.tobytes()
            self.compressed_publisher.publish(compressed)
            self.published_frames += 1

        # Keep a low-rate raw topic for tools that cannot consume compressed
        # images, without forcing DDS to move ~83 MB/s continuously.
        if frame_id % 6 == 0 and self.raw_publisher.get_subscription_count() > 0:
            raw = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            raw.header.stamp = stamp
            raw.header.frame_id = "camera3_optical_frame"
            self.raw_publisher.publish(raw)

    def report_stats(self):
        now = time.monotonic()
        elapsed = now - self.last_stats_time
        received = self.received_frames
        published = self.published_frames
        rx_fps = (received - self.last_stats_received) / elapsed
        pub_fps = (published - self.last_stats_published) / elapsed
        self.last_stats_time = now
        self.last_stats_received = received
        self.last_stats_published = published
        message = (
            f"GoPro health: receive={rx_fps:.1f} fps, "
            f"compressed_publish={pub_fps:.1f} fps, restarts={self.restart_count}"
        )
        # rclpy requires a call site to keep a fixed severity. Keep the INFO
        # and WARN calls on separate source lines so recovery does not crash
        # when the measured FPS crosses the threshold.
        if rx_fps >= 27.0:
            self.get_logger().info(message)
        else:
            self.get_logger().warning(message)

    def close(self):
        self.running = False
        self.stop_event.set()
        # Recovery owns this same lock while it replaces the decoder and
        # starts the camera. Final teardown must run after that transaction,
        # otherwise an in-flight recovery can resurrect a stream after close.
        with self.pipeline_lock:
            self._stop_decoder()
            if self.transport == "usb" and self.webcam is not None:
                try:
                    self.webcam.disable()
                except Exception as exc:
                    self.get_logger().warning(f"GoPro shutdown request failed: {exc}")
            elif self.transport == "wifi":
                try:
                    self._wireless_get("gopro/camera/stream/stop")
                except requests.RequestException:
                    pass
        # Never join a worker while holding the lock it may be waiting for.
        if hasattr(self, "reader_thread"):
            self.reader_thread.join(timeout=self.stall_timeout + 1.0)
        if hasattr(self, "publisher_thread"):
            self.publisher_thread.join(timeout=2.0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("serial", help="Last three characters of the GoPro serial number")
    parser.add_argument(
        "--transport",
        choices=("usb", "wifi"),
        default="usb",
        help="Camera transport (default: usb)",
    )
    parser.add_argument(
        "--host",
        default="10.5.5.9",
        help="GoPro HTTP address used by Wi-Fi mode",
    )
    parser.add_argument("--port", type=int, default=8554)
    parser.add_argument(
        "--camera-resolution",
        type=int,
        choices=(7, 12),
        default=7,
        help="GoPro webcam resolution enum: 7=720p (stable default), 12=1080p",
    )
    parser.add_argument(
        "--stall-timeout",
        type=float,
        default=5.0,
        help="Restart the USB stream when no complete frame arrives for this many seconds",
    )
    parser.add_argument(
        "--publish-fps",
        type=float,
        default=15.0,
        help="Latest-frame ROS publish rate (default: 15)",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=88,
        help="ROS compressed-image JPEG quality (default: 88)",
    )
    args = parser.parse_args()
    if not 1.0 <= args.publish_fps <= 60.0:
        parser.error("--publish-fps must be between 1 and 60")
    if not 70 <= args.jpeg_quality <= 100:
        parser.error("--jpeg-quality must be between 70 and 100")

    rclpy.init()
    node = None
    try:
        node = GoProCamera3(
            args.serial,
            args.port,
            args.camera_resolution,
            args.stall_timeout,
            args.transport,
            args.host,
            args.publish_fps,
            args.jpeg_quality,
        )
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

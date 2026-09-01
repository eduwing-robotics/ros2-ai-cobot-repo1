#!/usr/bin/env python3
"""HSV 물체 인식 + Depth로 카메라 기준 3D 좌표 계산.

hsv_object_detector.py에서 얻은 물체의 픽셀 중심 (cx, cy)에 depth 값과
camera intrinsics를 결합해서, pinhole camera model 역투영으로 카메라
좌표계 기준 실제 3D 좌표(mm)를 구한다.

color/depth 픽셀이 정확히 같은 지점을 가리켜야 하므로 realsense2_camera를
반드시 align_depth.enable:=true 옵션으로 launch해야 한다.

사전 준비:
  - ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
  - hsv_object_detector.py로 확인한 목표 물체 HSV 범위 (아래 LOWER_HSV/UPPER_HSV)

사용법:
  python3 hsv_depth_to_3d.py
  (ESC 키로 종료)
"""
import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image

# hsv_object_detector.py에서 확인한 목표 물체(파란색) HSV 범위
LOWER_HSV = np.array([100, 100, 50])
UPPER_HSV = np.array([130, 255, 255])

MIN_CONTOUR_AREA = 50

# depth 중심 픽셀 주변 (half*2+1)x(half*2+1) 패치의 중앙값을 사용
# (한 픽셀만 읽으면 depth 센서 노이즈로 0이나 튀는 값이 나올 수 있음)
DEPTH_PATCH_HALF = 3


class HSVDepthTo3D(Node):
    def __init__(self):
        super().__init__('hsv_depth_to_3d')
        self.bridge = CvBridge()
        self.color_frame = None
        self.depth_frame = None
        self.intrinsics = None  # (fx, fy, cx0, cy0)

        self.create_subscription(Image, '/camera/camera/color/image_raw', self.on_color, 10)
        self.create_subscription(
            Image, '/camera/camera/aligned_depth_to_color/image_raw', self.on_depth, 10)
        self.create_subscription(
            CameraInfo, '/camera/camera/aligned_depth_to_color/camera_info', self.on_info, 1)

        self.create_timer(0.03, self.on_timer)  # ~30Hz

    def on_color(self, msg):
        self.color_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    def on_depth(self, msg):
        # 16UC1: 픽셀당 2바이트 정수, 단위=mm (depth_check.py에서 확인한 것과 동일)
        self.depth_frame = np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)

    def on_info(self, msg):
        if self.intrinsics is None:
            fx, fy, cx0, cy0 = msg.k[0], msg.k[4], msg.k[2], msg.k[5]
            self.intrinsics = (fx, fy, cx0, cy0)
            self.get_logger().info(
                f'Intrinsics 수신: fx={fx:.1f}, fy={fy:.1f}, cx0={cx0:.1f}, cy0={cy0:.1f}')

    def on_timer(self):
        if self.color_frame is None or self.depth_frame is None or self.intrinsics is None:
            return

        frame = self.color_frame.copy()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, LOWER_HSV, UPPER_HSV)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > MIN_CONTOUR_AREA:
                moments = cv2.moments(largest)
                cx = int(moments['m10'] / moments['m00'])
                cy = int(moments['m01'] / moments['m00'])

                z = self._patch_median_depth(cx, cy)
                if z is not None:
                    fx, fy, cx0, cy0 = self.intrinsics
                    x = (cx - cx0) * z / fx
                    y = (cy - cy0) * z / fy
                    self.get_logger().info(
                        f'3D 좌표 (카메라 기준, mm): X={x:.1f}, Y={y:.1f}, Z={z:.1f}')
                else:
                    self.get_logger().warn('해당 지점의 유효한 depth 값을 찾지 못함')

                cv2.drawContours(frame, [largest], -1, (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

        cv2.imshow('Detection', frame)

        if cv2.waitKey(1) == 27:  # ESC
            rclpy.shutdown()

    def _patch_median_depth(self, cx, cy):
        h, w = self.depth_frame.shape
        y0, y1 = max(0, cy - DEPTH_PATCH_HALF), min(h, cy + DEPTH_PATCH_HALF + 1)
        x0, x1 = max(0, cx - DEPTH_PATCH_HALF), min(w, cx + DEPTH_PATCH_HALF + 1)
        patch = self.depth_frame[y0:y1, x0:x1]
        valid = patch[patch > 0]
        if valid.size == 0:
            return None
        return float(np.median(valid))


def main():
    rclpy.init()
    node = HSVDepthTo3D()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""HSV 물체 인식 + Depth 3D 좌표에 calib_transform_depth.npz를 적용해 로봇 base 좌표로 변환.

hsv_depth_to_3d.py에서 구한 카메라 기준 (X, Y, Z)에 회전행렬 R + 이동벡터 t를 적용한다:
P_robot = R @ P_camera + t (Kabsch 알고리즘, compute_calibration_depth.py와 동일 공식)

주의: 기존 14-2 ArUco+solvePnP 파이프라인이 쓰는 calib_transform.npz가 아니라
calib_transform_depth.npz를 쓴다 - compare_solvepnp_vs_depth.py에서 solvePnP와 depth
측정 방식이 같은 지점을 최대 68mm까지 다르게 재는 것을 확인했기 때문에, 캘리브레이션도
반드시 depth 방식(capture_calib_point_depth.py)으로 다시 만들어야 측정 방식이 통일되어
오차가 없어진다.

캘리브레이션을 depth로 통일한 뒤에도 Z에 약 55mm의 잔여 오차가 남았는데, 이는 depth가
물체 윗면(카메라 쪽 표면)을 재는 반면 그리퍼는 물체 중심/옆면 높이를 잡아야 해서 생기는
별개의 문제였다 (서로 다른 위치 3곳에서 실측 후 평균 - CORRECTION_X_MM/CORRECTION_Y_MM/
Z_GRASP_OFFSET_MM 값 참고). 이 보정값은 지금 쓰는 파란 물체 크기에 한정된 값이라
물체가 바뀌면 재측정이 필요하다.

사전 준비:
  - ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
  - capture_calib_point_depth.py + compute_calibration_depth.py로 calib_transform_depth.npz 생성 완료

사용법:
  python3 hsv_to_robot_coord.py
  (ESC 키로 종료)
"""
import os

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
DEPTH_PATCH_HALF = 3  # depth 중심 픽셀 주변 (half*2+1)x(half*2+1) 패치의 중앙값 사용

TRANSFORM_FILE = os.path.join(os.path.dirname(__file__), "calib_transform_depth.npz")

# 물체 표면(depth가 재는 지점) -> 실제 그립 위치 보정.
# depth는 물체의 카메라 쪽 윗면을 재는데, 그리퍼는 물체 중심/옆면 높이를 잡아야 해서
# 생긴 체계적 오차 - 서로 다른 위치 3곳에서 WebApp 실측값과 비교해 평균낸 상수
# (14-2의 마커->그립지점 보정과 같은 종류의 문제, 이 파란 물체 크기에 한정된 값)
CORRECTION_X_MM = -16.2
CORRECTION_Y_MM = 2.3
Z_GRASP_OFFSET_MM = 55.5


class HSVToRobotCoord(Node):
    def __init__(self):
        super().__init__('hsv_to_robot_coord')

        data = np.load(TRANSFORM_FILE)
        self.R = data['R']
        self.t = data['t']

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
        # 16UC1: 픽셀당 2바이트 정수, 단위=mm
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
                    cam_xyz_mm = np.array([
                        (cx - cx0) * z / fx,
                        (cy - cy0) * z / fy,
                        z,
                    ])
                    robot_xyz_mm = self.R @ cam_xyz_mm + self.t
                    robot_xyz_mm[0] += CORRECTION_X_MM
                    robot_xyz_mm[1] += CORRECTION_Y_MM
                    robot_xyz_mm[2] += Z_GRASP_OFFSET_MM

                    self.get_logger().info(
                        f'로봇 base 기준 좌표(mm, 보정 적용): '
                        f'X={robot_xyz_mm[0]:.1f}, Y={robot_xyz_mm[1]:.1f}, Z={robot_xyz_mm[2]:.1f}')
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
    node = HSVToRobotCoord()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

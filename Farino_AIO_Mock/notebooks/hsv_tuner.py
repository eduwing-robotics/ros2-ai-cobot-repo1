#!/usr/bin/env python3
"""HSV 색상 범위 튜닝 도구.

카메라에 목표 물체를 비춘 상태에서 트랙바를 조절하며 Mask 창에서
물체만 하얗게(255), 배경은 검게(0) 나오는 지점을 눈으로 찾는다.
이때의 H/S/V Min/Max 6개 값이 hsv_object_detector.py 등 이후
스크립트에서 쓸 목표 물체의 HSV 범위가 된다.

사전 준비:
  - ros2 launch realsense2_camera rs_launch.py

사용법:
  python3 hsv_tuner.py
  (ESC 키로 종료)
"""
import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image


def nothing(x):
    pass


class HSVTuner(Node):
    def __init__(self):
        super().__init__('hsv_tuner')
        self.bridge = CvBridge()
        self.frame = None
        self.create_subscription(Image, '/camera/camera/color/image_raw', self.on_image, 10)

        cv2.namedWindow('Trackbars')
        cv2.createTrackbar('H Min', 'Trackbars', 0, 179, nothing)
        cv2.createTrackbar('H Max', 'Trackbars', 179, 179, nothing)
        cv2.createTrackbar('S Min', 'Trackbars', 0, 255, nothing)
        cv2.createTrackbar('S Max', 'Trackbars', 255, 255, nothing)
        cv2.createTrackbar('V Min', 'Trackbars', 0, 255, nothing)
        cv2.createTrackbar('V Max', 'Trackbars', 255, 255, nothing)

        self.create_timer(0.03, self.on_timer)  # ~30Hz UI 갱신

    def on_image(self, msg):
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

    def on_timer(self):
        if self.frame is None:
            return

        hsv = cv2.cvtColor(self.frame, cv2.COLOR_BGR2HSV)
        lower = np.array([
            cv2.getTrackbarPos('H Min', 'Trackbars'),
            cv2.getTrackbarPos('S Min', 'Trackbars'),
            cv2.getTrackbarPos('V Min', 'Trackbars'),
        ])
        upper = np.array([
            cv2.getTrackbarPos('H Max', 'Trackbars'),
            cv2.getTrackbarPos('S Max', 'Trackbars'),
            cv2.getTrackbarPos('V Max', 'Trackbars'),
        ])
        mask = cv2.inRange(hsv, lower, upper)
        result = cv2.bitwise_and(self.frame, self.frame, mask=mask)

        cv2.imshow('Original', self.frame)
        cv2.imshow('Mask', mask)
        cv2.imshow('Result', result)

        if cv2.waitKey(1) == 27:  # ESC
            print(f'\n최종 HSV 범위 -> lower={lower.tolist()}, upper={upper.tolist()}')
            rclpy.shutdown()


def main():
    rclpy.init()
    node = HSVTuner()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""HSV 색상 + Contour 기반 물체 인식.

hsv_tuner.py로 찾은 목표 물체의 HSV 범위로 마스크를 만들고, 그 안에서
가장 큰 덩어리(contour)를 물체로 판단해 픽셀 중심 좌표 (cx, cy)를 계산한다.
이 (cx, cy)가 다음 단계(14-4: depth+intrinsics로 3D 카메라 좌표 변환)의 입력이 된다.

사전 준비:
  - ros2 launch realsense2_camera rs_launch.py
  - hsv_tuner.py로 목표 물체의 HSV 범위 확인 완료 (아래 LOWER_HSV/UPPER_HSV에 반영)

사용법:
  python3 hsv_object_detector.py
  (ESC 키로 종료)
"""
import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image

# hsv_tuner.py에서 확인한 목표 물체(파란색) HSV 범위
LOWER_HSV = np.array([100, 100, 50])
UPPER_HSV = np.array([130, 255, 255])

# 이보다 작은 덩어리는 노이즈로 간주하고 무시
# (물체가 카메라에서 멀어 픽셀상 크기가 작을 수 있어 50으로 낮춤 - 아까 hsv_tuner.py에서
#  본 노이즈 점은 면적이 1~수 px 수준이라 50이면 노이즈는 걸러지고 실제 물체는 통과함)
MIN_CONTOUR_AREA = 50


class HSVObjectDetector(Node):
    def __init__(self):
        super().__init__('hsv_object_detector')
        self.bridge = CvBridge()
        self.create_subscription(Image, '/camera/camera/color/image_raw', self.on_image, 10)

    def on_image(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, LOWER_HSV, UPPER_HSV)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)

            if area > MIN_CONTOUR_AREA:
                moments = cv2.moments(largest)
                cx = int(moments['m10'] / moments['m00'])
                cy = int(moments['m01'] / moments['m00'])

                self.get_logger().info(f'물체 중심 (pixel): ({cx}, {cy}), area={area:.0f}')

                cv2.drawContours(frame, [largest], -1, (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

        cv2.imshow('Detection', frame)
        cv2.imshow('Mask', mask)

        if cv2.waitKey(1) == 27:  # ESC
            rclpy.shutdown()


def main():
    rclpy.init()
    node = HSVObjectDetector()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

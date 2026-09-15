#!/usr/bin/env python3

import cv2
import cv2.aruco as aruco
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

MARKER_ID = 0


def main():
    rclpy.init()
    node = Node("check_aruco_detection")
    result = {}

    def on_image(msg):
        result["image"] = np.frombuffer(msg.data, dtype=np.uint8).reshape(
            msg.height, msg.width, 3
        )

    sub = node.create_subscription(Image, "/camera/camera/color/image_raw", on_image, 1)
    for _ in range(50):
        rclpy.spin_once(node, timeout_sec=0.2)
        if "image" in result:
            break

    if "image" not in result:
        print("카메라 이미지를 못 받았습니다. rs_launch.py가 실행 중인지 확인하세요.")
        node.destroy_node()
        rclpy.shutdown()
        return

    gray = cv2.cvtColor(result["image"], cv2.COLOR_RGB2GRAY)
    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    parameters = aruco.DetectorParameters_create()
    corners, ids, _ = aruco.detectMarkers(gray, dictionary, parameters=parameters)

    if ids is None or MARKER_ID not in ids.flatten():
        print(f"마커(ID={MARKER_ID})를 못 찾았습니다. 각도/거리/조명을 바꿔서 다시 시도하세요.")
    else:
        idx = list(ids.flatten()).index(MARKER_ID)
        c = corners[idx][0]
        side_px = np.linalg.norm(c[0] - c[1])  # 마커 한 변이 화면에서 몇 픽셀인지
        print(f"마커 인식 성공! 화면상 한 변 길이 ≈ {side_px:.1f}px")
        if side_px < 20:
            print("20px 미만입니다 - 인식은 됐지만 위치 정확도가 떨어질 수 있습니다. "
                  "가능하면 더 큰 마커나 더 가까운 거리를 권장합니다.")
        elif side_px < 40:
            print("40px 미만 - 동작은 하겠지만 여유가 크지 않습니다.")
        else:
            print("충분히 큰 크기로 인식됐습니다.")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
""" Eye-to-hand 3D 캘리브레이션 점 하나 캡처.

사용법:
  1. 로봇을 원하는 위치(X,Y,Z 자유롭게)로 이동시켜서 완전히 멈춘다.
  2. 이 스크립트를 실행한다 -> 약 1~2초간 여러 프레임(NUM_SAMPLES)에서 마커 pose를 모아
     중앙값을 낸 3D 위치(카메라 좌표계, mm)와 로봇의 실제 3D 위치(로봇 base 좌표계, mm)를
     calib_points_3d.json에 한 줄 추가한다. 이 구간 동안 로봇/마커는 완전히 정지 상태여야 한다.
  3. 최소 4곳(권장 10곳 이상, 다양한 X/Y/Z로) 반복한다.
     -> 이후 compute_calibration.py로 회전+이동 변환행렬 계산.

사전 준비:
  - ros2 launch realsense2_camera rs_launch.py rgb_camera.color_profile:=1920x1080x30
  - ros2 run fairino_hardware_v3_9_7 ros2_cmd_server (로봇 상태 피드백용)
  - 그리퍼 몸통에 ArUco 마커(ID=0, 실측 한 변 길이를 MARKER_LENGTH_M에 반영) 부착 완료
"""
import json
import os

import cv2
import cv2.aruco as aruco
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from fairino_msgs.msg import RobotNonrtState

MARKER_ID = 0
MARKER_LENGTH_M = 0.029  # 실측값(mm)을 m로 환산 - 마커 실측 후 반드시 갱신할 것
POINTS_FILE = os.path.join(os.path.dirname(__file__), "calib_points_3d.json")
NUM_SAMPLES = 30  # 이 프레임 수만큼 마커 pose를 모아 중앙값을 사용 (단일 프레임 노이즈 완화)
MAX_ATTEMPTS = 150  # NUM_SAMPLES를 채우기 위한 최대 spin 횟수 (검출 실패 프레임 대비 여유)


def main():
    rclpy.init()
    node = Node("capture_calib_point")
    result = {}

    def on_image(msg):
        result["image"] = np.frombuffer(msg.data, dtype=np.uint8).reshape(
            msg.height, msg.width, 3
        )
        result["image_seq"] = result.get("image_seq", 0) + 1

    def on_info(msg):
        result["K"] = np.array(msg.k).reshape(3, 3)
        result["D"] = np.array(msg.d)

    def on_state(msg):
        result["state"] = msg

    node.create_subscription(Image, "/camera/camera/color/image_raw", on_image, 1)
    node.create_subscription(CameraInfo, "/camera/camera/color/camera_info", on_info, 1)
    node.create_subscription(RobotNonrtState, "/nonrt_state_data", on_state, 1)

    for _ in range(50):
        rclpy.spin_once(node, timeout_sec=0.2)
        if all(k in result for k in ("image", "K", "state")):
            break

    if not all(k in result for k in ("image", "K", "state")):
        print("카메라/카메라정보/로봇상태 중 일부를 못 받았습니다. 노드 실행 상태를 확인하세요.")
        node.destroy_node()
        rclpy.shutdown()
        return

    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    parameters = aruco.DetectorParameters_create()

    # 여러 프레임에서 마커 pose를 모아 중앙값을 사용 (단일 프레임 노이즈 완화)
    # 이 구간 동안 로봇/마커가 완전히 정지해 있어야 함
    samples = []
    last_seq = -1
    attempts = 0
    while len(samples) < NUM_SAMPLES and attempts < MAX_ATTEMPTS:
        rclpy.spin_once(node, timeout_sec=0.1)
        attempts += 1
        if result.get("image_seq", 0) == last_seq:
            continue
        last_seq = result["image_seq"]

        gray = cv2.cvtColor(result["image"], cv2.COLOR_RGB2GRAY)
        corners, ids, _ = aruco.detectMarkers(gray, dictionary, parameters=parameters)
        if ids is None or MARKER_ID not in ids.flatten():
            continue

        idx = list(ids.flatten()).index(MARKER_ID)
        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
            [corners[idx]], MARKER_LENGTH_M, result["K"], result["D"]
        )
        samples.append(tvecs[0][0] * 1000.0)  # OpenCV는 m 단위 -> mm 환산

    if len(samples) < 5:
        print(
            f"마커(ID={MARKER_ID}) 검출 성공 프레임이 {len(samples)}개뿐입니다(최소 5개 필요). "
            "카메라 시야/각도를 확인하고 다시 시도하세요."
        )
        node.destroy_node()
        rclpy.shutdown()
        return

    samples = np.array(samples)
    cam_xyz_mm = np.median(samples, axis=0)
    stddev = samples.std(axis=0)
    print(
        f"마커 {len(samples)}프레임 중앙값 사용 "
        f"(프레임간 표준편차 mm: x={stddev[0]:.1f} y={stddev[1]:.1f} z={stddev[2]:.1f})"
    )

    state = result["state"]
    record = {
        "cam_x": float(cam_xyz_mm[0]),
        "cam_y": float(cam_xyz_mm[1]),
        "cam_z": float(cam_xyz_mm[2]),
        "robot_x": state.cart_x_cur_pos,
        "robot_y": state.cart_y_cur_pos,
        "robot_z": state.cart_z_cur_pos,
    }

    points = []
    if os.path.exists(POINTS_FILE):
        with open(POINTS_FILE) as f:
            points = json.load(f)
    points.append(record)
    with open(POINTS_FILE, "w") as f:
        json.dump(points, f, indent=2, ensure_ascii=False)

    print(
        f"기록됨 ({len(points)}번째 점): "
        f"camera=({record['cam_x']:.1f}, {record['cam_y']:.1f}, {record['cam_z']:.1f})mm  "
        f"robot=({record['robot_x']:.1f}, {record['robot_y']:.1f}, {record['robot_z']:.1f})mm"
    )
    print(f"저장 위치: {POINTS_FILE}")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

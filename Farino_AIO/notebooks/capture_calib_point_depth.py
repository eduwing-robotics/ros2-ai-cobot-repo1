#!/usr/bin/env python3
"""Eye-to-hand 3D 캘리브레이션 점 하나 캡처 - depth 센서 버전.

capture_calib_point.py(solvePnP 방식)와 목적은 같지만, 마커 위치를 depth 센서로
측정한다는 점만 다르다. compare_solvepnp_vs_depth.py에서 두 측정 방식이 같은
지점을 최대 68mm까지 다르게 재는 것을 확인했는데, 원래 calib_transform.npz는
solvePnP로 캘리브레이션됐으면서 HSV+depth 파이프라인(hsv_to_robot_coord.py)에는
그대로 적용해서 이 불일치가 그대로 오차로 나타났었다. 캘리브레이션도 depth로
다시 만들면 "캘리브레이션 때 측정 방식"과 "실전에서 측정 방식"이 통일되어
이 오차가 원천적으로 사라진다.

결과 파일을 calib_points_3d.json과 분리(calib_points_3d_depth.json)해서
기존 14-2 ArUco+solvePnP Pick&Place 파이프라인은 그대로 유지한다.

사용법:
  1. 로봇을 원하는 위치(X,Y,Z 자유롭게)로 이동시켜서 완전히 멈춘다.
  2. 이 스크립트를 실행한다 -> 약 1~2초간 여러 프레임(NUM_SAMPLES)에서 마커의 depth 기반
     위치(카메라 좌표계, mm)와 로봇의 실제 3D 위치(로봇 base 좌표계, mm)를 중앙값으로 내서
     calib_points_3d_depth.json에 한 줄 추가한다. 이 구간 동안 로봇/마커는 완전히 정지 상태.
  3. 최소 4곳(권장 10곳 이상, 다양한 X/Y/Z로) 반복한다.
     -> 이후 compute_calibration_depth.py로 회전+이동 변환행렬 계산.

사전 준비:
  - ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
  - ros2 run fairino_hardware_v3_9_7 ros2_cmd_server (로봇 상태 피드백용)
  - 그리퍼 몸통에 부착된 ArUco 마커(ID=0)가 카메라에 잘 보이는 상태
"""
import json
import os

import cv2
import cv2.aruco as aruco
import numpy as np
import rclpy
from fairino_msgs.msg import RobotNonrtState
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image

MARKER_ID = 0
POINTS_FILE = os.path.join(os.path.dirname(__file__), "calib_points_3d_depth.json")
NUM_SAMPLES = 30  # 이 프레임 수만큼 모아 중앙값 사용 (단일 프레임 노이즈 완화)
MAX_ATTEMPTS = 150
DEPTH_PATCH_HALF = 3  # 마커 중심 픽셀 주변 (half*2+1)x(half*2+1) 패치의 중앙값 사용


def main():
    rclpy.init()
    node = Node("capture_calib_point_depth")
    result = {}

    def on_color(msg):
        result["color"] = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        result["color_seq"] = result.get("color_seq", 0) + 1

    def on_depth(msg):
        result["depth"] = np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)

    def on_info(msg):
        result["K"] = np.array(msg.k).reshape(3, 3)

    def on_state(msg):
        result["state"] = msg

    node.create_subscription(Image, "/camera/camera/color/image_raw", on_color, 1)
    node.create_subscription(
        Image, "/camera/camera/aligned_depth_to_color/image_raw", on_depth, 1)
    node.create_subscription(CameraInfo, "/camera/camera/color/camera_info", on_info, 1)
    node.create_subscription(RobotNonrtState, "/nonrt_state_data", on_state, 1)

    for _ in range(50):
        rclpy.spin_once(node, timeout_sec=0.2)
        if all(k in result for k in ("color", "depth", "K", "state")):
            break

    if not all(k in result for k in ("color", "depth", "K", "state")):
        print("카메라/depth/camera_info/로봇상태 중 일부를 못 받았습니다. "
              "align_depth.enable:=true 로 launch했는지, ros2_cmd_server가 떠 있는지 확인하세요.")
        node.destroy_node()
        rclpy.shutdown()
        return

    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    parameters = aruco.DetectorParameters_create()

    samples = []
    last_seq = -1
    attempts = 0
    while len(samples) < NUM_SAMPLES and attempts < MAX_ATTEMPTS:
        rclpy.spin_once(node, timeout_sec=0.1)
        attempts += 1
        if result.get("color_seq", 0) == last_seq:
            continue
        last_seq = result["color_seq"]

        gray = cv2.cvtColor(result["color"], cv2.COLOR_RGB2GRAY)
        corners, ids, _ = aruco.detectMarkers(gray, dictionary, parameters=parameters)
        if ids is None or MARKER_ID not in ids.flatten():
            continue
        idx = list(ids.flatten()).index(MARKER_ID)

        cx, cy = corners[idx][0].mean(axis=0)
        cx, cy = int(round(cx)), int(round(cy))

        depth_frame = result["depth"]
        h, w = depth_frame.shape
        y0, y1 = max(0, cy - DEPTH_PATCH_HALF), min(h, cy + DEPTH_PATCH_HALF + 1)
        x0, x1 = max(0, cx - DEPTH_PATCH_HALF), min(w, cx + DEPTH_PATCH_HALF + 1)
        patch = depth_frame[y0:y1, x0:x1]
        valid = patch[patch > 0]
        if valid.size == 0:
            continue

        z = float(np.median(valid))
        K = result["K"]
        fx, fy, cx0, cy0 = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
        samples.append([(cx - cx0) * z / fx, (cy - cy0) * z / fy, z])

    if len(samples) < 5:
        print(
            f"마커(ID={MARKER_ID}) 검출/depth 성공 프레임이 {len(samples)}개뿐입니다(최소 5개 필요). "
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

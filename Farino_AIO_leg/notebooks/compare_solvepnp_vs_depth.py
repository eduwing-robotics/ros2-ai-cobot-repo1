#!/usr/bin/env python3
"""캘리브레이션에 쓴 solvePnP 방식 vs HSV 파이프라인의 depth 방식이
같은 지점을 얼마나 다르게 재는지 직접 비교.

로봇을 움직이거나 사람이 눈대중으로 정렬할 필요 없이, ArUco 타겟 마커(ID=1,
generate_target_marker.py로 생성) 하나만 놓고 같은 카메라 프레임에서 두 방식으로
동시에 위치를 계산해서 두 측정 방식 자체의 불일치만 순수하게 확인한다.

- solvePnP 방식: capture_calib_point.py와 동일 (마커 4개 코너 + 마커 실제 크기로 기하학적 계산,
  depth 센서 전혀 사용 안 함) - 캘리브레이션 때 쓴 것과 같은 방식
- depth 방식: hsv_depth_to_3d.py와 동일 (마커 중심 픽셀의 depth 센서 측정값 + intrinsics로 역투영)

사전 준비:
  - ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true
  - ArUco 타겟 마커(ID=1)를 평평한 곳에 고정

사용법:
  python3 compare_solvepnp_vs_depth.py
"""
import cv2
import cv2.aruco as aruco
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image

MARKER_ID = 1
MARKER_LENGTH_M = 0.029  # capture_calib_point.py와 동일 실측값
NUM_SAMPLES = 30
MAX_ATTEMPTS = 150
DEPTH_PATCH_HALF = 3


def main():
    rclpy.init()
    node = Node("compare_solvepnp_vs_depth")
    result = {}

    def on_color(msg):
        result["color"] = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        result["color_seq"] = result.get("color_seq", 0) + 1

    def on_depth(msg):
        # 16UC1: 픽셀당 2바이트 정수, 단위=mm
        result["depth"] = np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)

    def on_info(msg):
        result["K"] = np.array(msg.k).reshape(3, 3)
        result["D"] = np.array(msg.d)

    node.create_subscription(Image, "/camera/camera/color/image_raw", on_color, 1)
    node.create_subscription(
        Image, "/camera/camera/aligned_depth_to_color/image_raw", on_depth, 1)
    # color와 aligned_depth_to_color는 같은 픽셀 격자를 쓰므로 intrinsics(K)도 동일 -
    # solvePnP와 depth 역투영 양쪽에 이 K 하나만 재사용한다.
    node.create_subscription(CameraInfo, "/camera/camera/color/camera_info", on_info, 1)

    for _ in range(50):
        rclpy.spin_once(node, timeout_sec=0.2)
        if all(k in result for k in ("color", "depth", "K")):
            break

    if not all(k in result for k in ("color", "depth", "K")):
        print("카메라 이미지/depth/camera_info 중 일부를 못 받았습니다. "
              "align_depth.enable:=true 로 launch했는지 확인하세요.")
        node.destroy_node()
        rclpy.shutdown()
        return

    dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    parameters = aruco.DetectorParameters_create()

    pnp_samples = []
    depth_samples = []
    last_seq = -1
    attempts = 0
    while len(pnp_samples) < NUM_SAMPLES and attempts < MAX_ATTEMPTS:
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
        marker_corners = corners[idx]

        # --- solvePnP 방식 (마커 기하학, depth 미사용) ---
        rvecs, tvecs, _ = aruco.estimatePoseSingleMarkers(
            [marker_corners], MARKER_LENGTH_M, result["K"], result["D"]
        )
        pnp_samples.append(tvecs[0][0] * 1000.0)  # m -> mm

        # --- depth 방식 (마커 중심 픽셀의 depth 센서 측정값 사용) ---
        cx, cy = marker_corners[0].mean(axis=0)
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
        fx, fy, cx0, cy0 = result["K"][0, 0], result["K"][1, 1], result["K"][0, 2], result["K"][1, 2]
        depth_samples.append([(cx - cx0) * z / fx, (cy - cy0) * z / fy, z])

    if len(pnp_samples) < 5 or len(depth_samples) < 5:
        print(f"검출 성공 프레임이 너무 적습니다 (solvePnP={len(pnp_samples)}, depth={len(depth_samples)}). "
              "마커 각도/거리/조명을 확인하고 다시 시도하세요.")
        node.destroy_node()
        rclpy.shutdown()
        return

    pnp_xyz = np.median(np.array(pnp_samples), axis=0)
    depth_xyz = np.median(np.array(depth_samples), axis=0)
    diff = depth_xyz - pnp_xyz

    print(f"\nsolvePnP 방식 (n={len(pnp_samples)}): "
          f"X={pnp_xyz[0]:.1f}, Y={pnp_xyz[1]:.1f}, Z={pnp_xyz[2]:.1f} (mm)")
    print(f"depth   방식 (n={len(depth_samples)}): "
          f"X={depth_xyz[0]:.1f}, Y={depth_xyz[1]:.1f}, Z={depth_xyz[2]:.1f} (mm)")
    print(f"차이(depth-solvePnP): "
          f"dX={diff[0]:+.1f}, dY={diff[1]:+.1f}, dZ={diff[2]:+.1f} (mm)")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

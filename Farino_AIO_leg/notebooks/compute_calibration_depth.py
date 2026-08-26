#!/usr/bin/env python3
"""calib_points_3d_depth.json에 모인 3D 점 쌍으로 '카메라 좌표 -> 로봇 좌표' 변환(회전+이동)을 계산.

compute_calibration.py와 로직은 동일(Kabsch 알고리즘)하되, capture_calib_point_depth.py로
depth 센서 방식으로 수집한 점들을 사용한다는 점만 다름 - HSV+depth 파이프라인
(hsv_to_robot_coord.py) 전용 변환행렬을 만든다.

사용법: python3 compute_calibration_depth.py  (calib_points_3d_depth.json에 최소 10개 권장)
결과: calib_transform_depth.npz 저장 (R: 3x3 회전행렬, t: 이동벡터)
"""
import json
import os

import numpy as np

POINTS_FILE = os.path.join(os.path.dirname(__file__), "calib_points_3d_depth.json")
OUT_FILE = os.path.join(os.path.dirname(__file__), "calib_transform_depth.npz")

with open(POINTS_FILE) as f:
    points = json.load(f)

if len(points) < 4:
    print(f"점이 {len(points)}개뿐입니다. 최소 10개(권장 10개 이상) 필요 - capture_calib_point_depth.py로 더 모으세요.")
    raise SystemExit(1)

cam_pts = np.array([[p["cam_x"], p["cam_y"], p["cam_z"]] for p in points])
robot_pts = np.array([[p["robot_x"], p["robot_y"], p["robot_z"]] for p in points])

# --- Kabsch 알고리즘 ---
cam_centroid = cam_pts.mean(axis=0)
robot_centroid = robot_pts.mean(axis=0)
cam_centered = cam_pts - cam_centroid
robot_centered = robot_pts - robot_centroid

H = cam_centered.T @ robot_centered
U, S, Vt = np.linalg.svd(H)
d = np.sign(np.linalg.det(Vt.T @ U.T))
R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
t = robot_centroid - R @ cam_centroid

# 검증: 캘리브레이션에 쓴 점들을 다시 넣어 재투영 오차(mm) 확인
predicted = (R @ cam_pts.T).T + t
errors = np.linalg.norm(predicted - robot_pts, axis=1)

print(f"점 {len(points)}개로 계산 완료.")
print(f"재투영 오차(mm): min={errors.min():.1f} max={errors.max():.1f} mean={errors.mean():.1f}")
print("점별 오차(mm, 큰 순):")
for i in np.argsort(-errors):
    print(f"  {i + 1}번째 점: {errors[i]:.1f}mm")
if errors.mean() > 20:
    print(
        "평균 오차가 20mm를 넘습니다 - 점 개수를 늘리거나(10개 이상 권장), "
        "캡처 순간 로봇/마커가 완전히 멈춰 있었는지 확인하세요."
    )
else:
    print("오차가 양호한 범위입니다.")

np.savez(OUT_FILE, R=R, t=t)
print(f"저장 완료: {OUT_FILE}")

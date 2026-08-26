#!/usr/bin/env python3
"""Ch14 — 캘리브레이션 검증용 '가짜 물체' 타겟 마커 생성.

그리퍼에 붙인 마커(ID=0)와 겹치지 않도록 ID=1을 사용한다.
프린트해서 작업대(테이블) 위 평평한 곳, 카메라 시야 안에 고정해두면
vision_pick_and_place.py가 이 마커를 '집어야 할 물체' 대신으로 인식한다.

실행: python3 generate_target_marker.py
결과: 같은 폴더에 aruco_marker_1.png 생성
"""
import cv2.aruco as aruco
import cv2

TARGET_MARKER_ID = 1
SIDE_PIXELS = 400  # 출력용 이미지 한 변 픽셀 수 (인쇄 크기와는 무관, 프린터가 알아서 맞춤)

dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
marker_image = aruco.drawMarker(dictionary, TARGET_MARKER_ID, SIDE_PIXELS)

out_path = "aruco_marker_1.png"
cv2.imwrite(out_path, marker_image)
print(f"저장 완료: {out_path} (마커 ID={TARGET_MARKER_ID}, DICT_4X4_50)")
print("프린트한 뒤 작업대 위 평평한 곳(카메라 시야 안)에 '가짜 물체'로 놓아주세요.")
print("그리퍼 마커(ID=0)와 크기가 같아야 정확도가 비슷합니다 — 29mm(실측)로 인쇄하세요.")

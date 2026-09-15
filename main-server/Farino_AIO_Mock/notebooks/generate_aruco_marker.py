#!/usr/bin/env python3
"""Ch14 — 캘리브레이션/물체 인식용 ArUco 마커 이미지를 만들어서 저장한다.

실행: python3 generate_aruco_marker.py
결과: 같은 폴더에 aruco_marker_0.png 생성 -> 프린트해서 그리퍼 몸통(고정된 부분)에 부착
"""
import cv2.aruco as aruco
import cv2

MARKER_ID = 0
SIDE_PIXELS = 400  # 출력용 이미지 한 변 픽셀 수 (인쇄 크기와는 무관, 프린터가 알아서 맞춤)

dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
marker_image = aruco.drawMarker(dictionary, MARKER_ID, SIDE_PIXELS)

out_path = "aruco_marker_0.png"
cv2.imwrite(out_path, marker_image)
print(f"저장 완료: {out_path} (마커 ID={MARKER_ID}, DICT_4X4_50)")
print("프린트한 뒤 그리퍼 몸통(움직이지 않는 부분)에 평평하게 붙여주세요.")

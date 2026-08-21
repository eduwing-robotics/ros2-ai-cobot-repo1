# D435 1920×1080 Intrinsic 전용 25장 수집 계획

## 원칙

- ChArUco 보드는 작업대에 완전히 고정한다.
- D435는 `1920x1080@15`로 유지하고 카메라 거치대를 건드리지 않는다.
- 로봇 웹의 데카르트 이동만 사용하며 속도를 낮게 유지한다.
- 정확한 Base 이동 방향보다 rqt 화면에서 보드가 위치하는 영역이 중요하다.
- 보드 전체가 항상 보일 필요는 없지만 최소 corners 12개 이상이어야 한다.
- 같은 화면 구도를 여러 번 저장하지 않는다.
- 각 자세에서 로봇을 완전히 정지하고 한 번만 저장한다.

## 25개 화면 구도

| 번호 | rqt에서 보드 위치 | 카메라/보드 자세 | 거리 |
|---:|---|---|---|
| 1 | 중앙 | 정면 | 중간 |
| 2 | 왼쪽 | 정면 | 중간 |
| 3 | 오른쪽 | 정면 | 중간 |
| 4 | 위쪽 | 정면 | 중간 |
| 5 | 아래쪽 | 정면 | 중간 |
| 6 | 왼쪽 위 | 정면 | 중간 |
| 7 | 오른쪽 위 | 정면 | 중간 |
| 8 | 왼쪽 아래 | 정면 | 중간 |
| 9 | 오른쪽 아래 | 정면 | 중간 |
| 10 | 중앙 | Tool RY 약 -10° | 중간 |
| 11 | 중앙 | Tool RY 약 +10° | 중간 |
| 12 | 왼쪽 | Tool RY 약 -10° | 중간 |
| 13 | 오른쪽 | Tool RY 약 +10° | 중간 |
| 14 | 중앙 | Tool RX 약 -10° | 중간 |
| 15 | 중앙 | Tool RX 약 +10° | 중간 |
| 16 | 위쪽 | Tool RX 약 -10° | 중간 |
| 17 | 아래쪽 | Tool RX 약 +10° | 중간 |
| 18 | 중앙 | Tool RZ 약 -15° | 중간 |
| 19 | 중앙 | Tool RZ 약 +15° | 중간 |
| 20 | 왼쪽 | 복합 기울기 RX/RY 약 7° | 중간 |
| 21 | 오른쪽 | 반대 복합 기울기 RX/RY 약 7° | 중간 |
| 22 | 중앙 | 정면 | 가까움 |
| 23 | 왼쪽 또는 위쪽 | 약한 기울기 | 가까움 |
| 24 | 중앙 | 정면 | 멂 |
| 25 | 오른쪽 또는 아래쪽 | 약한 기울기 | 멂 |

가까움/멂은 충돌 없이 보드가 충분히 보이는 범위에서 중간 거리 대비 약
`±80~120 mm` 정도만 변화시킨다. 가장자리 구도에서는 보드를 이미지 경계에
딱 붙이지 말고 검은 외곽과 코너가 잘 보이게 여백을 둔다.

## 매 자세 저장 명령

번호에 맞춰 `--label`만 바꾼다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_intrinsic_capture.sh --label "01_center_front"
```

예:

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_intrinsic_capture.sh --label "10_center_ry_minus10"
/home/juchan-yoon/FR5_robot_control/calibration/run_intrinsic_capture.sh --label "22_center_near"
```

정상 출력:

```text
Saved intrinsic image N: ...
Total images: N (target 25)
```

## 25장 완료 후 계산

```bash
source /opt/ros/jazzy/setup.bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/calibrate_charuco_intrinsics.py
```

이 계산은 로봇을 움직이지 않고 후보 JSON만 생성한다. 후보를 활성화하거나
Hand-Eye 결과를 덮어쓰지 않는다.

## 화면 가장자리 보충 구도

첫 25장의 실제 보드 중심 분포가 화면 폭 38~60%, 높이 39~75%로 중앙에
집중되면 아래 8장을 추가한다. 좌표는 rqt의 1920x1080 원본 픽셀 기준이며
대략적인 목표다. 보드 전체와 검은 외곽이 잘리면 경계에서 조금 안쪽으로 둔다.

| 번호 | 목표 보드 중심 | 라벨 |
|---:|---|---|
| 26 | `(350, 540)` | `26_far_left_front` |
| 27 | `(1570, 540)` | `27_far_right_front` |
| 28 | `(960, 280)` | `28_far_top_front` |
| 29 | `(960, 800)` | `29_far_bottom_front` |
| 30 | `(350, 300)` | `30_far_top_left_tilt` |
| 31 | `(1570, 300)` | `31_far_top_right_tilt` |
| 32 | `(350, 780)` | `32_far_bottom_left_tilt` |
| 33 | `(1570, 780)` | `33_far_bottom_right_tilt` |

화면 좌우 구도는 기존 2/3번보다 약 4~5배 크게 옮겨야 한다. 로봇 좌표
수치보다 rqt에서 실제 보드 중심 위치를 기준으로 조절한다.

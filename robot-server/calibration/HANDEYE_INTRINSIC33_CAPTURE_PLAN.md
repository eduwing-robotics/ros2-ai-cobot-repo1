# Hand-Eye 재수집 계획 — 1920×1080 전용 intrinsic 고정

## 목적과 보존 원칙

- ChArUco 보드는 작업대에 완전히 고정한다.
- D435와 카메라 거치대는 수집 도중 절대 건드리지 않는다.
- 기존 데이터와 활성 Hand-Eye 결과는 삭제하거나 덮어쓰지 않는다.
- 새 데이터 파일은 `data/handeye_intrinsic33_samples.json`이다.
- 수집 시에는 원본 1920×1080 영상과 Base→Flange 자세를 저장한다. 계산 단계에서
  `camera_intrinsics_1920x1080_33images_candidate.json`을 고정하여 모든 영상의
  ChArUco pose를 다시 계산한다.

## 공통 안전 절차

1. FR5 WebApp에서 저장해 둔 높은 정면 관측 자세로 복귀한다.
2. 모든 상대 이동은 **그 기준 자세에서 새로 시작**한다. 직전 자세에서 연속으로
   각도나 이동량을 누적하지 않는다.
3. 평행 이동은 `Base`, 회전은 `Tool`의 Cartesian 이동을 사용한다.
4. 회전은 높은 관측 자세에서만 수행하고 속도는 5–10%로 둔다.
5. 보드가 영상 안에 있고 최소 corner 12개 이상인지 확인한다. 가능하면
   marker 17/17, corner 24/24 상태에서 저장한다.
6. 로봇 정지 후 1초 이상 기다린 다음 한 번 저장한다.

## 25개 자세

각 행은 항상 저장된 기준 자세에서 시작한다.

| 번호 | Base 평행 이동 | Tool 회전 |
|---:|---|---|
| 1 | 없음 | 없음 |
| 2 | 없음 | RY +8° |
| 3 | 없음 | RY -8° |
| 4 | 없음 | RY +14° |
| 5 | 없음 | RY -14° |
| 6 | 없음 | RX +8° |
| 7 | 없음 | RX -8° |
| 8 | 없음 | RX +14° |
| 9 | 없음 | RX -14° |
| 10 | 없음 | RZ +12° |
| 11 | 없음 | RZ -12° |
| 12 | Z +60 mm | 없음 |
| 13 | Z -40 mm | 없음; 충돌 여유 확인 후 5 mm씩 접근 |
| 14 | X +45 mm | RY +10° |
| 15 | X -45 mm | RY -10° |
| 16 | Y +40 mm | RX -10° |
| 17 | Y -40 mm | RX +10° |
| 18 | X +35, Y +30 mm | RX -8°, RY +8° |
| 19 | X -35, Y +30 mm | RX -8°, RY -8° |
| 20 | X +35, Y -30 mm | RX +8°, RY +8° |
| 21 | X -35, Y -30 mm | RX +8°, RY -8° |
| 22 | Z +45, X +30 mm | RY +12°, RZ +8° |
| 23 | Z +45, X -30 mm | RY -12°, RZ -8° |
| 24 | Z -30, Y +25 mm | RX -10°, RZ +8° |
| 25 | Z -30, Y -25 mm | RX +10°, RZ -8° |

보드 일부가 화면 밖으로 나가면 같은 부호를 유지하면서 각도를 2–3° 줄이거나,
Base X/Y로 보드를 화면 안에 다시 넣는다. 충돌 가능성이 있으면 해당 자세는
건너뛰고 안전한 반대 방향 조합으로 대체한다.

## 매 자세 저장 명령

새 터미널을 열었을 때 한 번 실행:

```bash
source /opt/ros/jazzy/setup.bash
source /home/juchan-yoon/FR5_robot_control/robot_ws/install/setup.bash
```

각 자세에서 아래 명령을 한 번씩 실행:

```bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/capture_charuco_handeye_sample.py \
  --frames 20 \
  --data-file /home/juchan-yoon/FR5_robot_control/calibration/data/handeye_intrinsic33_samples.json
```

정상 저장 예시는 `Saved ChArUco hand-eye sample N`이다. `Duplicate robot pose`가
나오면 저장되지 않은 것이므로 로봇 자세를 바꾸고 같은 번호를 다시 수행한다.

## 완료 조건

- `Total poses: 25` 이상
- 서로 다른 Flange 자세 25개
- 정면 자세만 반복하지 않고 RX/RY 양방향 회전 포함
- 수집이 끝나기 전까지 보드와 카메라 고정 상태 유지
- 수집 후에도 새 후보를 바로 활성화하지 않고 독립 검증 6자세로 먼저 평가

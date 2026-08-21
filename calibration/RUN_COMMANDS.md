# KSMC FR5 + D435 실행 명령 모음

## 1. ROS 환경 설정

새 터미널마다 먼저 실행한다.

```bash
source /opt/ros/jazzy/setup.bash
source /home/juchan-yoon/FR5_robot_control/robot_ws/install/setup.bash
```

## 2. FR5 ROS 명령 서버

별도 터미널에서 실행하고 계속 켜둔다.

```bash
source /opt/ros/jazzy/setup.bash
source /home/juchan-yoon/FR5_robot_control/robot_ws/install/setup.bash
ros2 run fairino_hardware_v3_9_7 ros2_cmd_server
```

## 3. D435 RGB 안정 모드

로봇을 수동 조그하면서 트레이 구도를 빠르게 확인할 때는 저지연 미리보기
모드를 사용한다. RGB 1280x720x30이며 Depth와 정렬을 끈다. 이 모드는 화면
조정 전용이고, 최종 좌표 계산이나 Hand-Eye 기반 파지 목표에는 사용하지 않는다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_d435_preview_low_latency.sh
```

구도 조정이 끝나면 미리보기 노드를 종료하고, 아래의 보정 조건과 일치하는
RGB 또는 RGB-D 모드로 다시 실행한다.

현재 ChArUco/ArUco 단계의 권장 실행 방법이다. RGB 1920x1080x15,
Depth 비활성, 시작 시 장치 reset을 사용한다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_d435_rgb_stable.sh
```

RealSense 노드는 동시에 두 개 실행하지 않는다.

부품 높이·3D 중심까지 필요할 때는 RGB-D 모드를 사용한다. Color 해상도는
동일하게 1920×1080×15로 유지하고 depth를 color frame에 정렬한다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_d435_rgbd_stable.sh
```

확인 토픽:

```bash
ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw
ros2 topic echo /camera/camera/color/camera_info --once
```

RGB 캘리브레이션/마커만 볼 때는 `run_d435_rgb_stable.sh`, 부품 접근과
AI/Vision 3D 결과가 필요할 때는 `run_d435_rgbd_stable.sh`를 사용한다.

## 4. ChArUco 마커·코너 화면

표시 노드:

```bash
source /opt/ros/jazzy/setup.bash
source /home/juchan-yoon/FR5_robot_control/robot_ws/install/setup.bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/view_charuco_board.py
```

다른 터미널에서 화면 열기:

```bash
source /opt/ros/jazzy/setup.bash
ros2 run rqt_image_view rqt_image_view \
  /calibration/charuco/image_annotated \
  --ros-args -p image_transport:=compressed
```

## 5. Hand-Eye refinement 샘플 저장

각기 다른 자세에서 한 번씩 실행한다.

```bash
source /opt/ros/jazzy/setup.bash
source /home/juchan-yoon/FR5_robot_control/robot_ws/install/setup.bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/capture_charuco_handeye_sample.py \
  --data-file /home/juchan-yoon/FR5_robot_control/calibration/data/handeye_refinement_samples.json
```

자세 계획은 `calibration/HANDEYE_REFINEMENT_POSES.md`를 따른다.

1920×1080 전용 intrinsic 33장 완료 후 새로 수집하는 데이터는 기존 파일과
분리하여 다음 명령을 사용한다.

```bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/capture_charuco_handeye_sample.py \
  --frames 20 \
  --data-file /home/juchan-yoon/FR5_robot_control/calibration/data/handeye_intrinsic33_samples.json
```

자세 순서는 `calibration/HANDEYE_INTRINSIC33_CAPTURE_PLAN.md`를 따른다.

## 6. 마커 중심 위 목표 계산만 하기

Dry-run은 로봇을 절대로 움직이지 않는다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_marker_target_dry_run.sh \
  --marker-id 8 \
  --approach-offset-mm 100 \
  --approach-frame base_z \
  --frames 20 \
  --dry-run
```

`base_z`는 마커를 Base 좌표로 변환한 다음 X/Y는 유지하고 Base Z에만
100 mm를 더한다. 기존 보드 법선 접근을 비교할 때만
`--approach-frame board_normal`을 사용한다.

## 7. 마커 중심 위 100 mm로 실제 이동

FR5를 AUTO 모드로 전환하고 Tool 1, 비상정지, 작업 공간을 확인한 뒤
실행한다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_marker_target_dry_run.sh \
  --marker-id 8 \
  --approach-offset-mm 100 \
  --approach-frame base_z \
  --frames 20 \
  --execute --confirm-move
```

`--marker-id 8`의 숫자만 원하는 보드 마커 ID로 변경한다. 이 명령은
마커 표면으로 자동 하강하거나 그리퍼를 작동하지 않는다.

## 8. 이동 속도 조절

이 스크립트는 `SetSpeed`와 `MoveCart`에 속도를 직접 전달한다. 따라서
FR5 WebApp 속도 슬라이더만 변경해도 이 이동 속도는 올라가지 않을 수 있다.

예: 안전 높이의 수평 이동을 40%, 자세 정렬·상승·하강을 15%로 설정:

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_marker_target_dry_run.sh \
  --marker-id 8 \
  --approach-offset-mm 100 \
  --approach-frame base_z \
  --frames 20 \
  --speed-percent 40 \
  --descent-speed-percent 15 \
  --execute --confirm-move
```

허용 범위:

```text
--speed-percent:            1~40% (수평 이동)
--descent-speed-percent:    1~25% (회전, 상승, 수직 접근; 권장 15~20%)
```

조금 느리게 하려면:

```text
--speed-percent 30 --descent-speed-percent 10
```

현재 기본값은 수평 40%, 나머지 안전 단계 15%다. 수직 단계는 필요하면 25%까지
현재 테스트 코드가 차단한다.

## 9. 독립 Hand-Eye 검증

```bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/validate_handeye_samples.py
```

로봇은 움직이지 않으며 저장된 독립 검증 자세의 X/Y/Z 및 3D 오차를
출력한다.

## 10. 동일 마커 멀티포즈 CSV 검증

ChArUco 보드를 고정한 채 로봇을 서로 다른 자세로 옮기고, 각 자세에서 같은
명령을 한 번씩 실행한다. 이 명령은 로봇을 움직이지 않는다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_handeye_multipose_validation.sh \
  --marker-id 8 \
  --frames 20
```

기본 결과는
`/home/juchan-yoon/FR5_robot_control/calibration/data/handeye_multipose_validation.csv`에 누적된다.
각 실행 후 평균/표준편차, 자세별 XYZ 및 3D 오차, 최대 오차, RMS와 회전
상관관계가 출력된다. 자세와 상세 기준은
`calibration/COORDINATE_DIAGNOSTIC.md`를 참고한다.

## 11. D435 1920×1080 intrinsic 전용 이미지 저장

자세 계획은 `calibration/INTRINSIC_1920_CAPTURE_PLAN.md`를 따른다. 한 자세당
아래 명령을 한 번 실행하고 label만 바꾼다.

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_intrinsic_capture.sh --label "01_center_front"
```

25장 완료 후 후보 intrinsic을 계산한다.

```bash
source /opt/ros/jazzy/setup.bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/calibrate_charuco_intrinsics.py
```

## 안전

- 실행 전에 항상 dry-run 결과를 먼저 확인한다.
- 좌표가 NaN/Inf이거나 큰 점프가 있으면 실행하지 않는다.
- `Ctrl+C`는 FR5 제어기가 이미 받은 동작을 취소하지 못할 수 있다.
- 이상 동작 시 FR5 WebApp Stop/Pause 또는 물리적 비상정지를 사용한다.

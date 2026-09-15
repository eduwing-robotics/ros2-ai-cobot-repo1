# S22 고정형 기판 좌표 캘리브레이션

S22 영상의 기판 중심을 FR5 `base` 평면 좌표로 바꾸는 고정형
Hand-to-Eye 절차다. 이 기능은 좌표만 계산하며 로봇 이동 명령을 보내지 않는다.

## 전제 조건

- S22의 거치 위치, 각도, 광학/디지털 줌을 최종 상태로 고정한다.
- FR5 `toolcoord1` TCP 캘리브레이션을 유지한다.
- S22 카메라와 FR5 상태 토픽이 같은 `ROS_DOMAIN_ID`에서 보여야 한다.
- 캘리브레이션 점은 같은 높이의 평면에 있어야 한다.
- 자동 조립에서는 S22 XY를 전역 보정으로 사용하고, 최종 높이와 근접 정밀
  보정은 D435 RGB-D가 담당한다.

## 1. 카메라·기판 검출 실행

USB scrcpy 고화질 카메라와 컨베이어 검출을 함께 실행한다.

```bash
~/KSMC/run_s22_conveyor_hq.sh
```

기존 컨베이어 노드는 검출된 기판의 외곽 4점을 해상도 독립 좌표로 발행한다.

```text
/vision/conveyor/assembly/board_polygon_normalized
/vision/conveyor/inspection/board_polygon_normalized
```

## 2. Base 기준점 수집

최소 4개, 권장 8개 이상의 점을 조립·검사 작업 영역 전체에 넓게 배치한다.
점들이 일직선에 있으면 안 되며, 영역 네 모서리와 내부를 포함한다.

각 점마다 다음을 반복한다.

1. FR5를 수동 Cartesian/Base 모드로 움직여 캘리브레이션된 TCP 끝을 실제
   기준점에 맞춘다.
2. 아래 명령에서 라벨만 변경한다.
3. 열린 S22 창에서 같은 물리 지점을 클릭한다.
4. 로봇이 정지한 상태에서 `S`를 눌러 저장한다. `Q`는 저장 없이 종료한다.

```bash
~/KSMC/vision_assembly/run_capture_s22_plane_point.sh --label P1
~/KSMC/vision_assembly/run_capture_s22_plane_point.sh --label P2
~/KSMC/vision_assembly/run_capture_s22_plane_point.sh --label P3
~/KSMC/vision_assembly/run_capture_s22_plane_point.sh --label P4
~/KSMC/vision_assembly/run_capture_s22_plane_point.sh --label P5
~/KSMC/vision_assembly/run_capture_s22_plane_point.sh --label P6
~/KSMC/vision_assembly/run_capture_s22_plane_point.sh --label P7
~/KSMC/vision_assembly/run_capture_s22_plane_point.sh --label P8
```

같은 라벨을 다시 저장하면 해당 점만 교체된다. 결과는
`vision_assembly/data/s22_plane_points.json`에 저장된다.

## 3. Homography 계산

```bash
~/KSMC/vision_assembly/run_calibrate_s22_plane.sh
```

기본 합격 기준은 XY RMS `2 mm` 이하, 최대 오차 `5 mm` 이하이며 기준점이
영상의 충분한 면적을 덮어야 한다. 실패한 결과는 저장되지만 좌표 노드가
사용하지 않는다.

결과 파일:

```text
~/KSMC/vision_assembly/data/s22_plane_calibration.json
```

## 4. 기판 Base 좌표 발행

컨베이어 카메라/ROI가 실행 중인 다른 터미널에서 실행한다.

```bash
~/KSMC/run_s22_board_localizer.sh
```

확인 토픽:

```bash
ros2 topic echo /vision/board/assembly_pose
ros2 topic echo /vision/board/assembly_position_valid
ros2 topic echo /vision/board/assembly_status
```

검사 위치는 `inspection`으로 이름만 바꾼 동일 토픽을 사용한다.
`PoseStamped` 위치 단위는 m이며 `frame_id`는 `base`다. 상태 JSON은 사람이
확인하기 쉽게 mm와 degree로도 값을 제공한다.

## 현재 안전 제한

- 기판 중심 XY는 캘리브레이션 범위 안에서만 유효하다. 범위 밖 외삽은
  `position_valid=false`가 된다.
- 현재 yaw는 기판 장축 기준 `180° modulo` 값이다. 지그 손잡이 기반 360° 방향
  판별을 실물 검증하기 전까지 `heading_valid=false`다.
- 이 좌표만으로 자동 배치를 실행하지 않는다. S22 위치와 D435 근접 보정을
  교차 검증한 뒤 Main Server가 동작을 허용해야 한다.

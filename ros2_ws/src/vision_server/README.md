# AI / Vision Server

3대 카메라 입력을 정리하고 YOLO 부품 검출 결과를 조립 수량 규칙과 비교해
검사 결과를 발행하는 ROS 2 Jazzy 패키지다. 물리적으로 Main Server와 같은
노트북에서 실행해도 소프트웨어 프로세스는 분리된다.

## 구성

```text
RGB cameras ─→ camera_manager ─→ part_detector ─→ assembly_inspector
                                      ↑   │               │
D435 aligned depth + CameraInfo ───────┘   ├→ /vision/status
                                           └→ 2D + camera-frame XYZ
```

| 노드 | 역할 |
|---|---|
| `camera_manager` | 실제 카메라 토픽을 일정한 이름으로 정리하고 카메라별 FPS 제한 |
| `part_detector` | YOLO 검출, 카메라 생존 상태, D435 aligned depth 기반 3D 후보점 발행 |
| `assembly_inspector` | 안정된 여러 프레임의 부품 수량과 검사 규칙 평가 |
| `conveyor_roi` | S22 영상에서 조립·비전검사 2개 정지선과 복수 기판 후단 추적 |
| `vision_mock` | 카메라·모델 없이 검출 결과 시험 |

## 토픽과 서비스

| 이름 | 내용 |
|---|---|
| `/vision/camera/d435` | D435 RGB 입력 |
| `/vision/camera/s22` | S22 RGB 입력 |
| `/vision/camera/gopro` | GoPro 전체 셀 입력 |
| `/vision/detections` | 카메라 ID가 포함된 부품 검출 목록 |
| `/vision/inspection` | PASS/FAIL, 클래스별 기대·검출 수량과 오류 |
| `/vision/status` | 모델 로드와 입력 카메라 상태 |
| `/vision/run_inspection` | 최신 S22 검출 결과로 검사를 실행하는 서비스 |
| `/vision/conveyor/stop_image/compressed` | 조립·검사 정지선과 기판 검출이 표시된 S22 영상 |
| `/vision/conveyor/assembly/stop_trigger` | 첫 번째 조립 정지선의 안정 통과 여부 |
| `/vision/conveyor/inspection/stop_trigger` | 두 번째 비전검사 정지선의 안정 통과 여부 |
| `/vision/conveyor/{station}/stop_line_normalized` | station별 영상 정규화 정지선 위치(0~1) |
| `/vision/conveyor/board_count` | 현재 영상에서 분리 검출한 기판 수 |
| `/vision/conveyor/station_spacing_valid` | 두 정지점에 기판 2장이 겹치지 않는 간격인지 여부 |
| `/vision/conveyor/station_spacing_board_lengths` | 정지선 간격을 현재 기판 진행축 길이로 나눈 값 |
| `/vision/conveyor/stop_line_ready` | 영상·검출·정지선 간격을 포함한 모터 허가 heartbeat |

기존 `/vision/conveyor/stop_trigger`, `/board_detected`,
`/stop_line_normalized` 토픽은 조립 station의 하위 호환 별칭이다. 새 코드는
station별 토픽을 사용한다.

## 카메라 역할

- **D435:** 근접 Pick, Depth, 위치 보정과 조립 후 근접 재검사
- **S22:** 기판 도착·회전, 전체 부품 수량과 최종 조립 검사
- **GoPro:** 전체 셀 모니터링. 초기 단계에서는 YOLO를 실행하지 않음

카메라 토픽과 역할은 `config/cameras.yaml`에서 변경한다. 장비 연결 후 실제
S22 및 GoPro 토픽 이름만 수정하면 나머지 노드 이름은 유지된다.

`/vision/status`의 `ready`는 모델 파일만 존재한다고 true가 되지 않는다.
설정에서 `required_for_ready: true`인 카메라 영상이 최근 2초 안에 실제로
도착해야 하며, `active_cameras`와 `missing_cameras`에서 상태를 확인할 수 있다.

### D435 depth 사용 범위

`part_detector`는 `/camera/camera/aligned_depth_to_color/image_raw`와 color
`CameraInfo`가 RGB 영상과 같은 해상도·시간 범위일 때만 검출 박스 중앙부의
robust median depth를 사용한다. 이때 `Part.depth_valid`와
`Part.position_valid`가 true가 되고, `camera_x_m/y_m/z_m`에 D435 color optical
frame 좌표가 기록된다. Depth가 꺼져 있거나 오래됐거나 RGB와 해상도가 다르면
2D 검출은 유지하되 3D 값은 invalid로 남긴다.

이 3D 점은 **안전 접근용 부품 중심 후보**다. 최종 grasp point는 근거리에서
contour/segmentation, 부품 방향, 그리퍼 폭과 Hand-Eye 변환을 함께 적용해 다시
확정해야 한다. 정렬되지 않은 depth pixel을 RGB box에 직접 대응하지 않는다.

## 부품 규칙

| YOLO 클래스 | 기대 수량 |
|---|---:|
| `gpu` | 1 |
| `hbm` | 8 |
| `black_block` | 5 |
| `cap_small` | 5 |
| `marked_white` | 2 |
| `long_orange` | 4 |
| **합계** | **25** |

검사는 클래스별 최소 confidence를 통과한 검출만 센다. 현재 규칙은 정확한
수량 일치, 알 수 없는 클래스 차단, 최근 3프레임 수량 안정성, 2초 timeout이다.
설정은 `config/parts.yaml`과 `config/inspection.yaml`에 있다.

수량 검사는 1차 기능이다. 위치·방향·슬롯 일치 검사는 실제 기판 CAD와 촬영
데이터가 준비되면 같은 `assembly_inspector`에 단계적으로 추가한다.

현재 구현된 판정은 `수량/클래스/confidence`까지다. 다음 항목은 아직 구현
완료로 간주하지 않는다.

- S22 기반 기판 도착 및 `T_base_camera_s22` 좌표 보정
- CAD slot별 위치 오차와 방향 오류
- 외관 손상/부품 자체 불량 분류
- D435 3D 후보점의 FR5 Base 변환과 폐루프 grasp 보정

## YOLO 준비

- 데이터 클래스 순서: `config/dataset.yaml`
- 추론 설정: `config/yolo.yaml`
- 모델 위치: `models/best.pt`
- YOLO 구현은 `detectors/yolo_backend.py`로 격리되어 추후 ONNX/TensorRT
  backend로 교체 가능하다.

모델이나 `ultralytics`가 없으면 `part_detector`는 강제 종료되지 않는다.
대신 `/vision/status`에 `model_loaded=false`를 발행한다.

## 빌드

```bash
cd ~/KSMC/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

## 장비 없는 Mock 검사

정상 25개:

```bash
ros2 launch vision_server mock.launch.py scenario:=pass
```

다른 터미널에서 결과 확인:

```bash
source /opt/ros/jazzy/setup.bash
source ~/KSMC/ros2_ws/install/setup.bash
ros2 topic echo /vision/inspection --once
```

HBM 1개 누락:

```bash
ros2 launch vision_server mock.launch.py scenario:=missing_hbm
```

지원 시나리오: `pass`, `missing_hbm`, `extra_gpu`, `low_score_hbm`, `unknown`.

## 실제 장비 실행

```bash
ros2 launch vision_server vision.launch.py
```

검사 실행 요청:

```bash
ros2 service call /vision/run_inspection std_srvs/srv/Trigger '{}'
```

실제 장비 단계에서는 D435/S22/GoPro 드라이버를 먼저 실행한 뒤 이 launch를
실행한다. Main Server는 영상 대신 `/vision/detections`,
`/vision/inspection`, `/vision/status`만 구독하면 된다.

## S22 컨베이어 2단 정지선 설정

컨베이어 상판이 준비되기 전에도 S22 영상에서 조립·비전검사 정지선을 조정할
수 있다. 표시·검출 노드는 모터 명령을 발행하지 않는다.

```bash
~/KSMC/ros2_ws/run_conveyor_roi.sh
```

RQT Image View에서 `/vision/conveyor/stop_image/compressed`를 선택한다. 영상
왼쪽→오른쪽을 기판 진행 방향으로 정의하며, 초록색은 조립 정지선, 하늘색은
비전검사 정지선이다. 기판 후단(왼쪽 끝)이 선택한 선을 안정적으로 통과할 때 해당
station trigger가 발생한다. 현재 조립선은 기존 실측값 `0.46055`, 검사선은 임시
`0.82`이며 최종 S22·컨베이어 고정 후 반드시 재조정한다.

노드는 어두운 직사각형 contour를 여러 개 유지하므로 두 기판을 동시에 추적할 수
있다. 두 선의 픽셀 간격이 `기판 진행축 길이 × 1.10 + 20 px`보다 작으면
`station_spacing_valid=false`, `stop_line_ready=false`가 되어 모터 제어를
차단한다. 이 조건이 두 정지점에 기판 2장이 겹치지 않게 하는 안전 검사다.

```bash
~/KSMC/ros2_ws/run_conveyor_stop_test.sh \
  --station assembly \
  --cmd-topic /cmd_vel \
  --cmd-type twist_stamped \
  --speed 0.02 \
  --timeout 15 \
  --execute --confirm-motion
```

이 시험 노드는 비전 heartbeat가 1초 이상 끊기거나, 정지 trigger가 발생하거나,
설정한 timeout에 도달하거나, 사용자가 Ctrl+C를 누르면 속도 0을 10회 발행한다.
`--timeout 0`은 시간 제한 없이 비전 trigger까지 구동한다.

현재 TurtleBot 설정(`TwistStamped`, 물리 전진=`linear.x=-0.10 m/s`)의 단계별
실행 명령은 다음과 같다.

```bash
# 1단계: 조립 정지선까지 이동
~/KSMC/run_conveyor_to_assembly.sh

# FR5 조립 완료와 작업영역 이탈을 사람이 확인한 뒤
# 2단계: 비전검사 정지선까지 이동
~/KSMC/run_conveyor_to_inspection.sh
```
각 명령은 선택한 한 정지선에서 종료된다. 아직 FR5 작업영역 interlock이 없으므로
조립 완료 후 자동 재출발은 금지했고 두 번째 명령을 명시적으로 실행해야 한다.
시험 속도는 최대 0.10 m/s로 제한한다.

D435 3D 결과가 필요할 때는 RealSense에서 depth와 color alignment도 켜야 한다.
RGB 전용 안정 실행 스크립트는 depth를 끄므로 그 상태에서는
`depth_valid=false`가 정상이다.

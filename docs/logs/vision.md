# AI/Vision 작업 기록

## 2026-08-13 — 6mm급 소형 부품 고해상도 OpenCV 검출

- 실제 출력 부품의 자 측정값은 약 `6.0 × 3.5 × 2.5 mm`; Unity/CAD 후보
  `cap_small`은 약 `6.80 × 3.84 × 3.02 mm`다.
- D435 RGB `1920×1080×15`에서 최종 자세의 marker 8 한 변은
  `104.25 px`, 국부 영상 스케일은 약 `0.1611 mm/px`였다.
- ChArUco top-view의 지정 검정 셀에서 contour와 `minAreaRect`로 중심·긴 축을
  검출하는 `calibration/scripts/detect_small_part_dry_run.py`를 추가했다.
- 0-based `column=2, row=2`에서 20/20프레임 검출에 성공했다. 추정 크기
  `7.624 × 4.356 mm`, 긴 축 `175.71°`, Board XY
  `[84.172, 84.623] mm`였다.
- 등록 높이 기반 Camera XYZ `[-6.979, -10.712, 212.499] mm`, Hand-Eye 적용
  Base XYZ `[-313.664, -58.659, -10.061] mm`였다.
- Base 반복성 중앙/최대 `0.013/0.069 mm`; 시각 검증 자료는
  `calibration/data/small_part_debug_verified/`에 저장했다.
- 2.5mm 높이는 depth 노이즈·동기화 영향이 커 이번에는 `depth invalid`였으며,
  검증된 board plane과 등록 부품 높이를 사용했다.

## 2026-08-13 — ROS 2 AI/Vision 서버 기반 구축

### 목적

- D435, Galaxy S22, GoPro의 역할을 분리하면서도 Main Server가 동일한 ROS 2
  인터페이스로 결과를 받을 수 있는 기반을 만든다.
- 실제 카메라와 학습 모델이 없는 환경에서도 부품 수량 및 PASS/FAIL 검사 흐름을
  먼저 검증한다.
- 이름은 팀명 접두사나 과도한 약어를 사용하지 않고 역할을 바로 이해할 수 있게
  정한다.

### 구성

```text
camera_manager → part_detector → assembly_inspector
                         └──────→ vision status
```

- ROS 2 패키지: `vision_interfaces`, `vision_server`
- 노드: `camera_manager`, `part_detector`, `assembly_inspector`, `vision_mock`
- 주요 토픽: `/vision/camera/d435`, `/vision/camera/s22`,
  `/vision/camera/gopro`, `/vision/detections`, `/vision/inspection`,
  `/vision/status`
- 검사 서비스: `/vision/run_inspection`

### 카메라 역할

- D435: 근접 Pick, aligned depth, 위치 보정, 조립 후 근접 재검사
- S22: 기판 도착·회전 확인, 전체 부품 수량, 최종 조립 검사
- GoPro: 전체 셀 관제 및 향후 보조 안전 감시. 초기 YOLO 대상에서는 제외

카메라가 발행하는 물리 토픽은 `cameras.yaml`에만 기록하고, 후속 노드는 위의
고정된 논리 토픽을 사용하도록 분리했다. 따라서 S22 연결 방식이 바뀌어도 검출·
검사 노드의 코드를 바꿀 필요가 없다.

### YOLO와 검사 규칙

- Ultralytics 구현은 `detectors/yolo_backend.py`로 격리했다. 추후 ONNX 또는
  TensorRT backend로 교체할 수 있다.
- 모델 기본 경로는 `models/best.pt`이며 모델이 없을 때 노드가 비정상 종료되지
  않고 `model_loaded=false` 상태를 발행한다.
- 조립 대상 규칙: GPU 1, HBM 8, 검정 블록 5, 소형 흰색·갈색 부품 5,
  표시 있는 흰색 부품 2, 긴 주황색 부품 4로 총 25개다.
- 현재 검사는 confidence, 클래스별 정확한 수량, 알 수 없는 클래스, 최근
  3프레임 안정성, 결과 timeout을 확인한다.
- 위치·방향·CAD slot 일치와 외관 불량 검사는 실제 모델 및 촬영 데이터가
  준비되면 `assembly_inspector`에 추가한다.

### 검증

- `colcon build --symlink-install` 빌드 성공
- 검사 규칙 단위 테스트 4개 통과
- Mock 정상 시나리오: `PASS 25/25`
- Mock HBM 1개 누락 시나리오: `FAIL 24/25`
- 실제 실행 Launch는 모델 파일이 없는 상태에서도 카메라 관리, 검출, 검사
  노드가 시작되고 모델 누락을 경고하도록 확인했다.

### 변경 파일

- `ros2_ws/src/vision_interfaces/`
- `ros2_ws/src/vision_server/`
- `ros2_ws/run_vision.sh`
- `ros2_ws/run_vision_mock.sh`

### 다음 작업

1. 장비 현장에서 S22와 GoPro의 실제 입력 토픽을 확인해 `cameras.yaml` 수정
2. 6개 부품 클래스의 실제·렌더·합성 데이터를 수집하고 라벨링
3. YOLO 학습 후 `models/best.pt` 배치 및 GPU 성능 측정
4. S22 기판 pose와 CAD slot 기반 위치·방향 검사 추가
5. D435 검출 결과에 aligned depth와 Hand-Eye Base 좌표를 결합

## 2026-08-13 — ChArUco 전체 검정 칸 소형 부품 자동 탐색

- 소형 부품 검출 범위를 특정 칸 `(2,2)`에서 ChArUco 보드의 모든 검정 칸으로 확장했다.
- 검정 칸 가장자리의 부품도 포함하도록 셀 ROI 여백을 12%에서 3%로 조정했다.
- 20프레임 수집 중 선택된 셀이 바뀌면 샘플을 폐기하고 다시 수집하도록 안정성 잠금을 추가했다.
- 옮긴 부품을 `(2,2)` 셀의 보드 좌표 `[92.746,72.102] mm`에서 재검출했다.
- 검출 외곽 크기 중앙값은 `7.722 x 4.367 mm`, Base 위치는
  `[-321.980,-71.312,-9.963] mm`, 프레임 jitter median/max는
  `0.013/0.074 mm`였다.
- 최신 결과를 `calibration/data/small_part_last.json`에 저장해 이동 단계가
  과거 하드코딩 좌표 대신 현재 검출 좌표를 읽을 수 있게 했다.

### 소형 부품 방향 좌표 추가

- 검출한 직사각형 장축을 ChArUco Board 좌표에서 Robot Base XY 좌표로
  회전 변환하고 `long_axis_angle_base_deg`로 저장하도록 확장했다.
- 현재 대각선 부품의 기존 영상에서는 Board 장축 45°가 검출됐지만, 변경 후
  재검증 시점에는 ChArUco 코너가 0개여서 새 결과 파일은 갱신하지 않았다.
- 보드가 다시 보이는 자세에서 재검출해야 방향 기반 이동을 사용할 수 있다.

### HSV 색상·크기·모양 결합 검출

- 소형 부품 후보를 밝기/크기만으로 고르던 방식에 HSV 색상 프로파일을 추가했다.
- 지원 프로파일: `light`(기본), `orange`, `brown`, `any`.
- 현재 밝은 베이지 부품을 `light` 프로파일로 검출했으며 median HSV는
  `[17,42,141]`, 셀 `(2,0)`, Base 위치는
  `[-318.692,-133.977,-9.937] mm`였다.
- 30프레임 Base jitter median/max `0.034/0.087 mm`로 안정 검출을 확인했다.
- 최대 Base jitter가 기본 0.5 mm를 초과하면 최신 목표 JSON을 갱신하지 않는
  안전 차단을 추가했다.
- 검정 부품은 검정 ChArUco 칸과 색 분리가 불가능하므로 밝은 트레이/배경 또는
  다른 검출 구성이 필요하다.

### 대각선 배치 XY 정밀도 개선

- 대각선에서만 커지는 XY 편차를 분석한 결과, 같은 프레임에서 회전 사각형
  중심과 contour centroid 차이는 약 0.2 px(약 0.03 mm)로 작았다.
- 보드 외곽 4점을 PnP로 재투영해 rectification하던 방식을, 검출된 ChArUco
  sub-pixel 코너 전체(최대 24개)에 대한 왜곡 보정 및 homography 방식으로
  변경했다. 작은 부품의 국소 XY와 대각선/셀 가장자리 편차를 줄이는 목적이다.
- Depth 조회 픽셀은 개선된 보드 좌표를 원래 왜곡 영상으로 다시 투영해 RGB와
  aligned depth의 픽셀 정의가 섞이지 않도록 했다.
- 변경 후 시험 시점에는 보드가 화면 밖에 있어 ChArUco 코너가 0개였으며,
  로봇을 보드 관측 자세로 복귀한 뒤 실영상 재검증이 필요하다.
- 실제 로봇 이동은 수행하지 않았고 기존 목표 JSON도 갱신하지 않았다.

## 2026-08-15 — 최신 Unity PCB Assembly Scene과 기존 좌표 비교

- `/home/hc/My project/Assets/Scenes/PcbAssemblyScene.unity`와
  `Assets/RobotArm/PcbPickCoordinates.csv`를 확인했다.
- 현재 Unity 메뉴 `Tools/Robot Arm/Build PCB Assembly Scene`은 prefab의 현재
  임의 배치를 그대로 추출하지 않고, `PcbAssemblySetup.cs`의 `SlotCentersMm`와
  `SlotYawDegrees`로 부품을 다시 슬롯에 배치한 뒤 CSV를 생성한다.
- 이전 KSMC 추출 좌표와 현재 CSV를 동일한 PCB 좌상단 기준으로 변환해 비교한
  결과, HBM 8개와 대부분의 슬롯은 최대 약 `0.001 mm` 차이로 사실상 동일했다.
- GPU 중심은 이전 대비 약 `1.60 mm` 차이가 났다.
- 기존 4개 흰색·갈색 소형 부품 슬롯은 현재 SMD Capacitor 01~04로 이름이
  바뀌었고 각 위치가 약 `0.76 mm` 차이 났다.
- 현재 모델에는 이전 파일에 없던 SMD Capacitor 05가 추가되어 총 25개가 되었고,
  이전 추출 모델은 24개였다.
- 기존 좌표의 `left_black_block`, `long_orange`, `right_white_black`은 현재
  Unity 모델에서 각각 VRM, Power Module, Inductor라는 이름으로 대응되지만,
  물리적 XY 위치는 동일한 슬롯으로 확인됐다.
- 현재 CSV의 `rotation_y_deg`는 Unity 루트 transform 회전값이고, 이전 JSON의
  `long_axis_deg_in_board`는 부품 형상 장축 방향이므로 두 값을 직접 비교하면
  안 된다. 높이값도 이전 JSON의 bounds 후보와 현재 렌더러 top-center 기준이
  달라 별도 실측이 필요하다.

## 2026-08-17 — S22 컨베이어 ROI 설정 노드 구현

- 컨베이어 상판이 준비되기 전에도 화면 구성을 진행할 수 있도록 S22 compressed
  영상에 `PRE-STOP`과 `STOP / ASSEMBLY` ROI를 표시하는 `conveyor_roi` 노드를
  추가했다.
- ROI는 입력 해상도에 종속되지 않는 0~1 비율 좌표로 관리하며 설정 파일은
  `vision_server/config/conveyor_roi.yaml`이다.
- 표시 영상 `/vision/conveyor/roi_image/compressed`, 두 픽셀 ROI와 영상 준비
  상태 토픽을 발행한다.
- 현재 단계는 시각적 위치 설정 전용이며 컨베이어 속도나 로봇 명령을 전혀
  발행하지 않는다. S22와 컨베이어가 최종 고정된 뒤 ROI를 확정하고 도착 검출과
  감속·정지 상태 머신을 연결한다.
- ROS 2 패키지 빌드 성공, ROI 좌표 변환 단위 테스트 `3 passed`, 노드 기동을
  확인했다.

### 첫 정지 시험용 단일 ROI로 단순화

- 사용자 요청에 따라 주황색 `PRE-STOP` 영역과
  `/vision/conveyor/prestop_roi` publisher를 제거했다.
- 초록색 `STOP / ASSEMBLY` ROI는 최초 세로형 설정 후, 기판이 기본적으로 가로
  방향으로 진입한다는 실제 조건에 맞춰 화면 비율
  `x=0.11, y=0.54, width=0.78, height=0.32`의 가로형으로 바로잡았다.
- 1920x1080 입력에서 가로형 ROI는 `x=211, y=583, width=1498,
  height=346 px`로 발행된다.
- 이 단계에서는 `/cmd_vel` publisher를 만들지 않아 TurtleBot 바퀴는 움직이지
  않는다. ROI 위치 확정 후 기판 진입 감지 dry-run을 먼저 연결한다.

### 박스 대신 기판 후단 통과 정지선으로 변경

- 기판 크기와 방향 변화에 박스 비율을 계속 맞추는 대신, 컨베이어 진행 방향과
  수직인 경계선을 두고 기판 후단이 통과하는 순간 정지하는 방식으로 변경했다.
- 기존 주황 영역이 왼쪽, 초록 영역이 오른쪽이었던 화면 구조를 근거로 초기 진행
  방향을 영상 왼쪽→오른쪽으로 정의하고 화면 폭 70% 지점에 세로선을 표시했다.
- 새 표시 토픽은 `/vision/conveyor/stop_image/compressed`, 정지선 위치는
  `/vision/conveyor/stop_line_normalized`, 준비 상태는
  `/vision/conveyor/stop_line_ready`다.
- 실제 S22 프레임에서 밝은 알루미늄 구조물 위에서도 보이도록 검정 외곽선과
  초록 중심선, 노란 진행 방향 화살표를 확인했다.
- 다음 단계는 기판 외곽 검출 결과의 후단 X 좌표를 여러 프레임 안정화해 정지선
  통과 trigger를 발행하는 dry-run이며, 아직 `/cmd_vel`은 발행하지 않는다.

### 실물 기판 현재 위치를 정지 기준으로 등록

- 사용자가 원하는 최종 정지 위치에 실물 기판을 놓은 S22 1920x1080 프레임에서
  기판 외곽과 후단을 측정했다.
- 어두운 직사각형, 면적, 종횡비, 직사각형 충실도 조건으로 기판을 검출하고 내부
  검색영역을 사용해 상단 검정 장비와 알루미늄 프레임 오검출을 분리했다.
- 현재 기판 후단은 약 `788~790 px`였으며 정지선 위치를 화면 폭의 `0.411`
  (`약 789 px`)로 확정했다.
- 실영상 dry-run에서 `board_detected=true`, 후단-정지선 오차 약 `3 px` 이내,
  5프레임 안정 조건 후 `stop_trigger=true`를 확인했다.
- 주석 화면에 파란 기판 외곽, 빨간 후단 십자, 남은 픽셀 거리와 dry-run trigger를
  추가했다. 아직 TurtleBot `/cmd_vel` 명령은 발행하지 않는다.

#### OpenCV ChArUco API 호환 및 재검증

- 현재 OpenCV의 `CharucoBoard`가 `getChessboardCorners()` 대신
  `chessboardCorners` 속성을 제공해 발생한 `AttributeError`를 수정했다.
- 두 API를 모두 자동 지원하도록 호환 분기를 추가했다.
- 대각선 부품을 30프레임 재검출한 결과 셀 `(3,1)`, Board XY
  `[127.520,39.701] mm`, Base XYZ `[-356.810,-103.374,-9.579] mm`,
  Base jitter median/max `0.023/0.053 mm`로 정상 완료했다.

### S22 컨베이어 최종 정지 위치 재등록

- 사용자가 기판을 실제로 멈추길 원하는 위치로 다시 옮긴 뒤 64프레임의 기판
  후단 X를 측정했다. 측정값은 약 `883.64~883.89 px`, 대표값은
  `883.8 px`로 안정적이었다.
- 1920픽셀 영상 기준 정지선을 `position=0.46055`로 변경했다
  (`0.46055 × 1919 ≈ 883.8 px`). 앞서 기록한 `0.411`은 기판을 옮기기 전의
  임시 위치이며 현재 설정으로 대체한다.
- 실제 컨베이어 모터 명령은 아직 연결하지 않고, 검출·정지 트리거만 확인하는
  dry-run 안전 단계로 유지한다.
- 재시작 뒤 확인한 한 프레임에서는 기판의 진행방향 후단(왼쪽 끝)이 영상 밖으로
  잘려 `BOARD NOT DETECTED`가 되었다. 저장한 883.8 px 기준은 유지하되, 카메라를
  고정하고 기판 전체가 프레임 안에 보이는 상태에서 최종 재검증한 뒤 모터 정지와
  연결해야 한다.

## 2026-08-20 — 최신 Unity 기판·부품 좌표 재계산

- `/home/hc/My project/Assets/RobotArm/PcbPickCoordinates.csv`의 최신 Unity
  export를 다시 읽었다. 모델 기판은 `140.000 × 110.337 mm`, 실물 기판은
  `139.000 × 110.000 mm`로 적용했다.
- Unity 좌측 최소 모서리 원점을 실물 기판 중심 원점으로 변환하고 X/Y 축별
  스케일 `139/140`, `110/110.337`을 적용했다.
- GPU 1, HBM 8, Power Module 4, VRM 5, Inductor 2, SMD Capacitor 5의 총
  25개 ID가 중복 없이 존재하는지 검증했다. 이전에 누락됐던 SMD Capacitor 05가
  포함됐다.
- 90도 회전 부품은 기판 축 기준 footprint X/Y를 교환해 충돌 검사가 실제 방향을
  반영하도록 했다. 모든 중심과 회전 footprint가 139×110mm 기판 내부임을 확인했다.
- 재생성 파일은 `board_layout_from_unity.{json,csv,svg}`와
  `assembly_layout_approx.json`이다. 반복 변환 도구는
  `tools/import_unity_pick_coordinates.py`다.
- Unity 좌표는 CAD 후보이므로 기존 `physical_board.json`의 D435 실측 SMD
  override는 덮어쓰지 않았다. 로봇 자동 배치 전 TCP 상공 검증이 필요하다.

## 2026-08-20 — S22 조립·검사 2중 정지선 비전

- 단일 기판/단일 정지선 검출을 복수 기판 contour와 `assembly`, `inspection`
  정지선 2개를 독립 추적하는 구조로 확장했다.
- 조립선은 기존 실측 정규화 위치 `0.46055`를 보존했고 검사선은 최종 장비 설치
  전 임시값 `0.82`로 두었다. 두 위치는 YAML에서 독립 조정할 수 있다.
- 현재 검출 기판의 진행축 픽셀 길이를 이용해 정지선 간격이
  `1.10 × 기판 길이 + 20 px` 이상인지 검사한다. 부족하면 비전 ready와 모든
  station trigger를 차단한다.
- station별 trigger·후단·거리 토픽과 전체 기판 수, 간격 유효성 토픽을 추가했다.
  기존 단일 정지선 토픽은 assembly 호환 별칭으로 유지했다.
- 표시 영상에는 조립선(초록), 검사선(하늘색), 검출 기판 수, station별 남은 거리,
  간격 정상/오류를 한 화면에 정리했다.
- 이 단계에서는 S22 실영상과 실제 기판 2장을 사용한 현장 검증을 하지 않았다.
  최종 고정 후 두 기판이 동시에 완전히 보이는 구도에서 선 위치를 재등록해야 한다.

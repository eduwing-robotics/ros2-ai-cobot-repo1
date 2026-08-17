# 카메라 작업 기록

## 2026-08-12 — D435 ChArUco 검출 깜빡임

- 목적: 정면 기준 자세에서 ChArUco 17개 마커와 24개 코너의 안정 검출.
- 증상: 로봇과 보드가 정지해 있어도 주석 화면의 마커가 프레임마다 깜빡임.
- 확인 결과: D435 RGB가 `640x480@30`으로 실행됐고 Depth도 활성화돼 있었다.
- 원인 후보: 40 cm 부근에서 16.8 mm 마커를 640x480으로 촬영해 마커 경계의
  픽셀 수가 부족해진 것. 검출 알고리즘 문제가 아니라 입력 해상도 조건 차이다.
- 이전 안정 조건: RGB `1920x1080@15`, Depth/align 비활성, RealSense 노드 1개.
- 사용자가 요청한 최소 변경: 현재 일반 실행 구성에서 RGB 프로파일만
  `1920x1080x15`로 바꾸고 Depth 기본 설정은 유지한다. 변경 적용에는 카메라
  노드 재시작이 필요하다.
- 권장 정밀 캘리브레이션 조건: USB 대역폭과 프레임 손상을 줄이기 위해
  `calibration/run_d435_rgb_stable.sh`의 RGB-only 모드 사용.
- 검증 기준: `/camera/camera/color/camera_info`가 1920x1080인지 확인하고,
  주석 화면에서 `markers 17/17`, `corners 24/24`가 안정적으로 유지되는지 본다.
- 주의: RealSense 노드를 동시에 두 개 실행하지 않는다.

## 2026-08-12 — 캘리브레이션 해상도 이력

- 기존 적용 Hand-Eye 40개 및 기존 독립 검증 5개 원본: `640x480`.
- 새 refinement 15개 및 현재 멀티포즈 검증: `1920x1080`.
- Extrinsic은 물리적으로 해상도와 무관하지만 각 해상도의 intrinsic과 코너
  정밀도가 ChArUco pose에 영향을 주어 Hand-Eye 추정값에 편향이 들어갈 수 있다.
- 이후 정밀 캘리브레이션과 독립 검증은 `1920x1080@15`로 통일한다.

## 2026-08-12 — 1920 intrinsic 전용 수집 절차

- Hand-Eye 영상에서 intrinsic을 동시에 추정하는 실험 편향을 줄이기 위해
  intrinsic 전용 저장 코드와 25구도 계획을 추가했다.
- 화면 중앙/상하좌우/네 모서리, RX/RY/RZ 기울기, 가까움/멂을 분산해
  1920x1080 color lens의 전체 영상 영역을 제약한다.
- 저장 코드: `calibration/scripts/capture_charuco_intrinsic_image.py`.
- 계산 코드: `calibration/scripts/calibrate_charuco_intrinsics.py`.
- 자세 계획: `calibration/INTRINSIC_1920_CAPTURE_PLAN.md`.
- 출력은 비활성 후보이며 기존 CameraInfo와 Hand-Eye를 자동 변경하지 않는다.

### 첫 intrinsic 수집 16장 폐기 보관

- 1~16번까지 저장한 뒤 사용자가 구도 오류를 확인해 처음부터 재수집하기로 했다.
- 해당 JSON과 원본 16장은 삭제하지 않고
  `calibration/archive/intrinsic_1920_discarded_20260812_1323/`로 이동했다.
- 활성 `calibration/data/intrinsic_1920_images.json`과 이미지 폴더가 없는 초기
  상태임을 확인했다. 다음 저장은 자동으로 sample 1부터 시작한다.
- Hand-Eye, 독립 검증, 기존 intrinsic 후보에는 변경이 없다.

### 재수집 sample 14 개별 제거

- 재수집 중 `14_center_rx_minus10` 구도가 잘못 저장돼 활성 JSON에서 14번
  항목만 제거했다.
- 원본 이미지는 삭제하지 않고
  `calibration/archive/intrinsic_1920_removed_samples_20260812/`
  `sample_014_center_rx_minus10_wrong.jpg`로 이동했다.
- 활성 데이터는 13개이며 다음 촬영은 다시 sample 14로 저장된다.

### Intrinsic 재수집 25장 중간 품질 판정

- 25장 모두 1920x1080, markers 17/17, corners 24/24, 라벨 중복 없음.
- 선명도 범위는 약 `67.7~98.6`으로 검출 품질은 양호하다.
- 실제 코너 중심 분포는 화면 폭의 `38.4~59.7%`, 높이의 `39.3~75.4%`로
  좌우 렌즈 가장자리 영역이 부족했다. 보드 면적도 `3.76~7.06%`였다.
- 예비 intrinsic RMS는 `0.0981 px`로 낮지만 왜곡계수 `k2=1.223`,
  `k3=-4.878`처럼 크게 추정돼 중앙 집중 데이터의 과적합 가능성이 있다.
- 후보는 활성화하지 않고 화면 좌우/모서리 중심 약 18~82%를 겨냥한 8장
  보충 계획(26~33)을 추가했다.
## 2026-08-12 — D435 1920×1080 전용 내부 파라미터 촬영 완료

- ChArUco 내부 파라미터 이미지 33장 수집 완료 (`intrinsic_1920_images.json`).
- 전 이미지 1920×1080, marker 17/17, corner 24/24 검출.
- 보드 중심 분포: 영상 폭 18.7–83.1%, 높이 26.2–77.0%, 면적 3.07–16.86%.
- 33장 후보: RMS 0.1664 px, `fx=1379.742`, `fy=1383.632`, `cx=968.874`, `cy=572.415`.
- 중앙 영상만 사용한 후보는 가장자리 영상에서 큰 오차가 발생했지만, 33장 후보는 전체/가장자리 재투영 오차가 각각 약 0.162/0.176 px로 안정적이었다.
- 파일: `calibration/data/camera_intrinsics_1920x1080_33images_candidate.json` (아직 활성화하지 않음).
## 2026-08-12 — D435 aligned depth 기반 RGB-PnP 거리 검증

- 현재 depth profile은 `848x480x30`, color-depth align은 최초 비활성 상태였다.
- 런타임 파라미터 `align_depth.enable=true`를 적용하여
  `/camera/camera/aligned_depth_to_color/image_raw` 발행을 확인했다.
- marker ID 8 중심에서 30프레임 RGB ChArUco PnP와 aligned depth를 비교했다.
- PnP Z 중앙값 `533.040 mm`, depth Z 중앙값 `532.000 mm`, 차이
  `-1.040 mm`이며 최대 절대 차이는 `1.071 mm`였다.
- 공장 CameraInfo 기반 RGB 거리 스케일은 현재 정면 자세에서 약 1 mm 안으로
  depth와 일치한다. 33장 자체 추정 intrinsic이 만든 약 12 mm 거리 증가는
  실제 depth와 맞지 않으므로 해당 후보를 사용하지 않는다.
- 진단 스크립트: `calibration/scripts/check_charuco_depth_consistency.py`.
### 기울기 양방향 depth 교차 검증

- Tool RY +10°: PnP/depth Z `517.266/517.000 mm`, 중앙 차이 `-0.284 mm`,
  최대 절대 차이 `1.304 mm`.
- Tool RY -10°: PnP/depth Z `530.635/531.000 mm`, 중앙 차이 `+0.372 mm`,
  최대 절대 차이 `1.386 mm`.
- 정면과 RY 양방향 모두 RGB-PnP 깊이가 aligned depth와 약 1.4 mm 이내로
  일치하므로, 기존 멀티포즈 Base 좌표 편차의 주원인은 RGB 깊이 스케일이 아니다.

## 2026-08-12 — 제조 셀 3대 카메라 역할 확정

- D435는 Eye-in-Hand Pick/Place 정밀 보정, depth 높이, 불확실 ROI 근접 재검사
  전용으로 사용한다.
- Galaxy S22는 조립 스테이션 수직 상부 고정형 주 검사 카메라로 사용한다.
  기판 도착·정지, board X/Y/yaw, 조립 완료 후 누락·위치·방향·오부품·표면
  이상 PASS/FAIL을 담당한다.
- GoPro HERO11은 상단 모서리 사선의 전체 공정 기록 및 사람/장애물 보조 감시를
  담당하며 정밀 좌표와 최종 품질 판정에는 사용하지 않는다.
- S22 최종 검사 전 FR5를 camera-clear 자세로 이동하고, S22에서 불확실한
  slot만 D435가 근접 재검사하는 계층형 검사 방식을 채택했다.
- 세부 배치와 불량별 담당표: `docs/CAMERA_ROLE_ARCHITECTURE.md`.

### S22 고정형 좌표계 역할 보완

- S22도 intrinsic과 `T_base_camera_s22`를 별도로 보정하면 고정형 Eye-to-Hand
  카메라로 FR5 Base 좌표를 계산할 수 있다.
- S22는 평면 기판/slot의 Base XY와 yaw를 제공하고, 단안 영상에 부족한 Z/높이는
  board plane, part recipe, D435 aligned depth로 보완한다.
- D435 근접 시 측면 장착 오프셋으로 목표가 FOV에서 사라지는 문제는 S22 전역
  좌표 + D435 마지막 유효 근접 측정 + 저속 단거리 하강으로 대응한다.
- D435 화면에 TCP가 보일 필요는 없으며 Hand-Eye와 FR5 TCP가 Camera-TCP 관계를
  제공한다. 두 카메라 Base 결과는 단순 평균하지 않고 차이가 크면 이동을 막는다.

### S22 컨베이어 도착·정지 검출 역할

- S22 영상에서 pre-stop ROI와 assembly target line/pose를 검출해 ROS
  conveyor controller에 오차를 제공한다.
- 목표점 근처에서는 저속으로 전환하고, 여러 프레임 동안 위치 오차와 영상 속도가
  모두 기준 안일 때만 정지 완료와 `assembly/ready`를 발행한다.
- 영상 timeout이나 기판 재이동이 발생하면 ready를 취소하고 컨베이어 정지 및
  FR5 조립 금지를 유지한다.

## 2026-08-13 — 3대 카메라 연결 방식과 지연 관리 원칙

- D435는 RGB-D 대역폭과 지연 안정성을 위해 노트북의 USB 3.x 포트에 직접
  연결한다. 현장에서는 `lsusb -t`의 `5000M` 이상 표시로 SuperSpeed 연결을
  확인한다.
- S22는 5 GHz Wi-Fi의 압축 영상으로 시작한다. 조립 완료 후 검사는 기판이
  정지한 상태라 수백 ms 지연을 허용할 수 있지만, 컨베이어 정지는 지연만큼
  오버슈트가 생기므로 pre-stop 감속과 정지 후 board pose 재측정을 유지한다.
- S22 영상은 1920x1080@15 FPS를 초기 목표로 하고, board arrival ROI는 가능한
  전체 15 FPS를 사용한다. YOLO 수량 검사는 정지 후 수행하므로 현재 5 FPS
  처리 제한을 유지할 수 있다.
- 현재 `gopro_camera3`는 Wi-Fi가 아니라 USB-C 가상 네트워크의 UDP Webcam
  stream을 FFmpeg로 디코딩한다. GoPro를 Wi-Fi로 바꾸지 않고 현재 USB 연결을
  유지한다.
- 영상 토픽은 compressed, QoS는 BEST_EFFORT/KEEP_LAST 1, 처리기는 항상 최신
  프레임 우선으로 구성해 오래된 프레임이 queue에 쌓이지 않게 한다.
- GoPro는 관제·기록용이며 네트워크 영상 기반 사람 검출은 보조 정지 계층일
  뿐 물리 비상정지나 안전 장치를 대체하지 않는다.
- 장비 연결 후 `ros2 topic hz`, `ros2 topic bw`, ping jitter와 실제 화면
  stopwatch 시험으로 FPS·대역폭·종단 지연을 각각 측정한다.

### 빈 기판 자체 특징 기반 좌표 검출 사전 확인

- D435 compressed RGB 토픽에서 현재 1920x1080 빈 기판 영상을 직접 저장해
  확인했다. 로봇 이동은 수행하지 않았다.
- 기판 외곽의 큰 직사각형과 네 모서리에 배치된 8개의 원형 체결 구멍이 선명해
  ArUco 없이도 기판 중심, 평면 회전(yaw), 원근 자세를 검출할 수 있는 형상이다.
- 좌우/상하 방향 혼동을 막으려면 비대칭 금색 패드 배치까지 방향 특징으로 함께
  사용한다. 외곽선만 사용하면 180도 방향 모호성이 생길 수 있다.
- 영상 좌표를 실제 기판 좌표와 FR5 Base 좌표로 변환하려면 체결 구멍 중심 간
  거리 또는 CAD상의 정확한 기준점 치수가 필요하다.
- 마커 없는 일반 RGB 프레임 진단용 `capture_color_frame.py`를 추가했다.

### 139×110 mm 빈 기판 좌표 dry-run 구현 및 실기 검증

- Unity 후보 크기 140×110.33742 mm와 사용자가 측정한 실물 139×110 mm를
  분리해 `vision_assembly/config/physical_board.json`에 기록했다.
- D435 RGB에서 검정 외곽 사각형을 찾고 139×110 mm 평면 PnP를 수행한 뒤
  `T_base_board=T_base_flange@T_flange_camera@T_camera_board`로 Base 좌표를
  계산하는 `detect_board_pose.py`를 추가했다. 로봇 이동 명령은 없다.
- 실제 1920×1080 영상 20프레임 검증 결과:
  Camera 중심 `[8.784, 3.998, 210.286] mm`, Base 중심
  `[297.307, -223.097, -7.146] mm`.
- Base 반복성 표준편차 `[0.040, 0.003, 0.066] mm`, median reprojection
  error 2.911 px로 측정됐다. 이는 같은 자세에서의 영상 반복성이며 실제 절대
  배치 정확도를 뜻하지 않는다.
- 디버그 영상에서 검출 외곽이 실물 기판 경계와 일치하는 것을 확인했다.
- 외곽 사각형만으로는 180도 방향 모호성이 있으므로 금색 패드 비대칭 방향
  판별 전까지 자동 배치에는 사용하지 않는다.

### 기판 정방향 확정 및 실시간 중심 오버레이

- 사용자가 빈 기판을 180도 회전한 현재 방향을 실제 조립의 정방향으로
  확정했다. 같은 화면 오른쪽의 완성 기판도 동일 방향임을 확인했다.
- 정방향은 빈 기판에서 큰 금색 패드 군집이 오른쪽 위에 보이는 방향으로
  정의하고 `physical_board.json`에 기록했다.
- 여러 기판이 동시에 보여도 색상 점유율이 가장 낮은 빈 기판을 선택하고,
  완성 기판은 `ASSEMBLED/OTHER`로 제외하는 `board_view` 노드를 추가했다.
- 출력 토픽 `/vision/board/image/compressed`에 빈 기판 외곽, 빨간 중심 십자,
  canonical 방향 판정, 중심 pixel 및 FR5 Base XYZ를 실시간 표시한다.
- 실제 화면에서 왼쪽 빈 기판 중심 십자와 외곽 검출이 맞고 오른쪽 완성 기판이
  제외되는 것을 확인했다. 노드는 로봇 이동 명령을 보내지 않는다.
- 기준 원본과 검증 오버레이 이미지를 `vision_assembly/data/reference/`에
  보관했다.

#### 기판 축·Yaw 및 조립 허용 상태 표시

- 중심 십자는 영상 수직·수평으로 고정하고 기판 회전과 분리했다.
- 기판 canonical +X를 파란 화살표, +Y를 노란 화살표로 표시하고 영상 기준
  `YAW(image)`를 추가했다.
- 정책을 `canonical=READY`, `rotated_180_corrected=READY`, `unknown=CHECK`로
  변경했다. 180도 회전은 좌표축을 canonical 방향으로 자동 정규화한다.
- 실기 화면에서 기판이 약 -3.74도 기울어진 상태를 canonical/READY로 판정하고,
  중심 십자는 고정된 채 축 화살표만 기판 외곽을 따라 회전하는 것을 확인했다.
- 산업 적용에서는 지그·키 구조로 역방향 유입을 예방하고, 평면 180도 회전은
  비전 판정 후 좌표 보정 또는 반송한다. 앞뒤 반전은 조립하지 않고 반송한다.

#### 기판 오검출 억제와 정보 패널 개선

- 어두운 선·그림자를 기판으로 오인하지 않도록 139:110 외곽 비율,
  rectangularity 0.78 이상, 모서리 원형 체결 구멍 최소 6개를 동시에 요구한다.
- 방향은 상단 두 구역 비교 대신 canonical 빈 기판의 금색 패드 4분면 분포
  `[0.053, 0.390, 0.300, 0.257]`와 0도/180도 가설을 비교한다.
- 현재 실기 화면은 holes=8, rect=0.98, dirErr=0.01로 READY를 통과했다.
- 저장 프레임을 180도 회전한 오프라인 시험에서
  `rotated_180_corrected`로 판정되고 canonical 축으로 정규화됨을 확인했다.
- 좌측 상단 텍스트를 반투명 패널 한 개로 정리하고 상태, orientation, yaw,
  center, geometry 진단값, Base XYZ를 줄맞춤해 표시한다.
- 중복 실행된 구버전 `board_view` 2개를 종료하고 최신 노드 하나만 실행했다.

#### Unity 소형 부품 슬롯 오버레이

- 6×3.5×2.5 mm 밝은 부품을 Unity의 `cap_small/right_white_brown` 후보로
  연결했다. Unity nominal은 약 6.80×3.84×3.02 mm다.
- Unity 중심 좌표를 실물 139×110 mm 축척으로 보정해 빈 기판 영상에 S1~S4
  슬롯을 투영했다. S1은 자주색 큰 십자, 나머지는 청록색으로 표시한다.
- 실기 화면에서 S1~S4가 빈 기판 왼쪽 세로 슬롯 열에 투영되는 것을 확인했다.
- 현재 S1 Base 후보는 `[149.1, -249.0, -4.3] mm`로 표시됐다. 이는 아직
  화면 확인용이며 로봇 이동 명령은 보내지 않았다.
- 실제 완성 기판에는 5개가 있지만 Unity 조립 파일에는 4개만 있어 다섯 번째
  슬롯은 좌표 미확정 상태를 유지한다.

#### 실물 배치로 소형 슬롯 5개 좌표 교정

- 사용자가 빈 기판의 실제 슬롯 5개에 밝은 소형 부품을 직접 배치했다.
- 정규화된 1390×1100 기판 영상에서 5개 밝은 부품 중심을 검출해 기판 중심
  기준 실물 좌표를 측정했다:
  P1 `[-41.88,-39.67]`, P2 `[-60.63,-17.60]`,
  P3 `[-60.41,-1.26]`, P4 `[-61.46,15.66]`,
  P5 `[-60.99,33.66] mm`.
- Unity의 기존 S1은 실제 슬롯이 아니므로 폐기했다. Unity S2~S4는 P2~P4와
  대체로 대응했고, 아래 외삽 B가 P5와 대응했다. P1은 위쪽 체결 구멍 앞의
  별도 X 위치다.
- 다섯 좌표를 `physical_board.json`의 `physical_slot_overrides`에 저장하고,
  화면 표시를 P1~P5로 교체했다.
- 실기 오버레이에서 P1~P5 십자가가 수동 배치한 부품 중심과 일치하는 것을
  확인했다. 당시 P1 Base 후보는 `[129.8,-253.7,-4.1] mm`였다.
- 아직 로봇 이동은 수행하지 않았으며, 실제 접근 전 다중 프레임 안정화와
  P1 상공 dry-run 검증이 필요하다.

#### P1 안정 좌표 저장

- `board_view`가 선택된 슬롯의 Base `PoseStamped`를
  `/vision/board/target_pose`로 발행하도록 추가했다.
- P1을 30프레임 수집해 Base XYZ `[74.082,-247.455,-4.141] mm`를 저장했다.
- 프레임 흔들림 median/max는 `0.083/0.226 mm`였다.
- 결과는 `vision_assembly/data/board_target_last.json`에 저장했다. 로봇 이동은
  수행하지 않았다.
# 2026-08-14 — 기판 인식 오버레이 가독성 개선

- 상단 보드 상태, 방향, yaw, 중심 픽셀, 선택 타겟, Base XYZ 및 Target XYZ를
  하나의 반투명 정보 패널 안에 정렬했다.
- 타겟 표시의 하드코딩된 `P1` 문구를 제거하고 실제 선택된 P1~P5 번호가
  표시되도록 수정했다. 타겟이 없으면 `NONE`으로 표시한다.
- 보드 +X/+Y 라벨을 각 화살표 끝 바깥쪽으로 이동하고 어두운 배경을 추가해
  축 선과 글자가 겹치지 않도록 개선했다.

## 2026-08-14 — P1 흰 종이 기준 슬롯 중심 1차 등록

- 사용자가 실제 부품 크기의 흰 종이를 P1 중심에 배치했다.
- 저장된 RQT 스크린샷에서 종이 외곽 중심과 기존 P1 십자 중심을 분리 측정했다.
- 기존 P1은 종이 중심 대비 기판 좌표로 약 `X -0.93 mm`, `Y -0.46 mm`에 있어
  P1을 `[-41.88,-39.67]`에서 `[-40.95,-39.21] mm`로 보정했다.
- 스크린샷 축소 영상 기반 1차 값이므로 원본 프레임 기반 최종 검증 전까지
  provisional로 취급한다.

### P2 흰 종이 기준 1차 등록

- P2에 세로로 배치한 흰 종이 외곽 중심과 기존 P2 십자 중심을 비교했다.
- 기존 P2 십자는 종이 중심 대비 기판 좌표로 약 `X -0.20 mm`, `Y +0.37 mm`에
  있어 P2를 `[-60.63,-17.60]`에서 `[-60.43,-17.97] mm`로 보정했다.
- P1과 동일하게 저장된 RQT 스크린샷 기반 provisional 값이다.

### P3 흰 종이 기준 1차 등록

- P3의 흰 종이 중심 대비 기존 십자는 기판 좌표로 약 `X -0.43 mm`,
  `Y +0.12 mm`에 있었다.
- P3를 `[-60.41,-1.26]`에서 `[-59.98,-1.38] mm`로 보정했다.
- 저장된 RQT 스크린샷 기반 provisional 값이다.

### P4 흰 종이 기준 1차 등록

- P4의 흰 종이 중심 대비 기존 십자는 기판 좌표로 약 `X -1.07 mm`,
  `Y +0.07 mm`에 있었다.
- P4를 `[-61.46,15.66]`에서 `[-60.39,15.59] mm`로 보정했다.
- 저장된 RQT 스크린샷 기반 provisional 값이다.

### P5 흰 종이 기준 1차 등록

- P5의 흰 종이 중심 대비 기존 십자는 기판 좌표로 약 `X -0.74 mm`,
  `Y +1.19 mm`에 있었다.
- P5를 `[-60.99,33.66]`에서 `[-60.25,32.47] mm`로 보정했다.
- 저장된 RQT 스크린샷 기반 provisional 값이다.

## 2026-08-14 — 전체 조립 부품 대략 배치 등록

- 완성 배치 상태의 D435 원본 1920×1080 프레임을
  `vision_assembly/data/all_parts_layout_raw.jpg`로 저장했다.
- 부품 이름과 개수를 GPU 1, HBM 8, Power Module 5, VRM 2, Inductor 4,
  SMD Capacitor 5로 통일했다.
- 기존 Unity 배치와 139×110 mm 실물 기판 축척을 대조해 기판 중심 기준 대략
  좌표를 `vision_assembly/config/assembly_layout_approx.json`에 저장했다.
- 기존 P1~P5는 `SMD Capacitor` 슬롯으로 이름을 변경했으며 흰 종이 보정값을
  유지했다.
- 최종 테이블 및 S22 설치 후 전체 좌표를 다시 정밀 등록해야 한다.

### 전체 부품 슬롯 오버레이 표시

- 기판 화면에 전체 25개 슬롯을 표시하도록 확장했다.
- 화면 혼잡을 줄이기 위해 `G=GPU`, `H=HBM`, `P=Power Module`, `V=VRM`,
  `I=Inductor`, `S=SMD Capacitor`와 번호 조합으로 표시한다.
- 기존 P1~P5의 P는 단순 Placement Point 의미였으며, 이제 S1~S5로 변경했다.
- 부품 종류별 색상을 분리하고 일반 마커/라벨 크기를 줄였으며 선택 목표만
  분홍색과 큰 마커로 강조한다.
- 기판 X/Y 화살표 선 굵기와 화살촉을 축소했다. 끝점 위치는 아래 사용자 피드백
  반영 항목에서 최종적으로 기판 외곽 108%로 변경했다.

#### 실물 VRM 위치 및 축 끝점 수정

- VRM은 S2 위쪽에 있는 흰색·검정 무늬 부품 2개임을 사용자 확인으로
  확정했다.
- 실물 영상 기준 VRM 대략 좌표를 `[-60.70,-45.00]`,
  `[-60.70,-33.60] mm`로 수정했다.
- X/Y 축은 사용자 요청에 따라 기판 경계의 108% 길이로 확장해 화살표 끝이
  기판 외곽보다 약간 바깥에 위치하도록 변경했다.
- 노란 Inductor 위의 노란 라벨이 보이지 않던 문제를 해결하기 위해 I1~I4
  마커와 글자 색상을 대비가 큰 밝은 파란색으로 변경했다.
- `+X` 축 라벨의 수직 여백을 12 px에서 24 px로 늘려 X축 선과 화살촉에
  겹치지 않도록 위치를 조정했다.
- 전체 부품 약어 라벨에 4 px 검정 외곽선을 먼저 그리고 2 px 밝은 색 본문을
  겹쳐 배경 대비를 높였다.
- 라벨 크기를 0.46에서 0.50으로 확대하고 오버레이 JPEG 품질을 88에서 95로
  올려 분홍·파랑·연두 계열 글자의 번짐을 줄였다.
- 초기 빈 기판 후보 선택용 `EMPTY`/`ASSEMBLED/OTHER` 문구는 완성 기판에서도
  잘못 표시되어 오버레이에서 제거했다. 향후 검사 단계의 실제 PASS/FAIL 상태로
  대체한다.

## 2026-08-14 — 스마트폰 DroidCam camera2 임시 연결 검증

- 개인 휴대폰 DroidCam을 Wi-Fi `192.168.11.12:4747`로 먼저 연결하고 Linux
  `v4l2loopback` 장치 `/dev/video10`에 매핑해 영상 경로를 검증했다.
- Ubuntu의 `v4l2loopback-dkms 0.12.7`은 현재 커널에 포함된 더 최신 모듈
  `0.15.3`과 충돌해 제거했으며, 커널 기본 모듈을 사용했다.
- 공식 DroidCam Linux CLI를 빌드해 `/usr/local/bin/droidcam-cli`로 설치했다.
- DroidCam의 YU12 출력이 ROS 2 `v4l2_camera`에서 지원되지 않는 문제를 확인하고,
  OpenCV 변환 기반 `camera2_ros_node.py`를 추가했다.
- 검증 결과 S22 영상은 `1280x720`, 약 `30 FPS`로 안정 수신됐다.
- ROS 2 토픽은 `/camera2/image_raw`, `/camera2/image_raw/compressed`,
  `/camera2/camera_info`로 통일했다.
- 현재 설치는 임시 배치 영상 시험용이다. S22를 최종 위치에 단단히 고정한 뒤
  intrinsic 및 Hand-to-Eye calibration을 별도로 수행해야 로봇 좌표 계산에
  사용할 수 있다.

### 프로젝트용 S22 USB 연결

- 프로젝트용 S22는 `SM-S901N`, ADB serial `R5CT32WHE9V`로 USB 디버깅 연결을
  확인했다.
- DroidCam ADB 방식으로 `/dev/video10`에 연결하고 기존 `/camera2` ROS 토픽을
  그대로 유지했다.
- S22의 Wi-Fi 주소는 `192.168.11.7:4747`이며 개인 휴대폰 주소와 분리했다.
- USB 전용 재실행 스크립트 `camera2_droidcam/run_camera2_usb.sh`를 추가했다.
- 초기 `1280x720`, JPEG 품질 85 영상이 확대 시 흐려 보여 가상 카메라의 기존
  형식 고정을 해제하고 `1920x1080`, JPEG 품질 95로 상향했다.
- 1080p ROS compressed 토픽에서도 실측 약 30 FPS를 유지해 S22 작업 카메라의
  기본 실행 설정으로 저장했다.
- Vision Server의 S22 입력 토픽을 실제 프로젝트용 DroidCam 토픽
  `/camera2/image_raw/compressed`로 수정했다. 기존 `/s22/image/compressed`는
  현재 사용하지 않는다.

## 2026-08-17 — S22 Wi-Fi/USB 동시 실패 복구

- `/dev/video10`과 `v4l2loopback`은 정상인 반면 Wi-Fi용과 USB용
  `droidcam-cli` 프로세스가 동시에 남아 같은 가상 카메라를 점유한 것을
  확인했다.
- Wi-Fi `192.168.11.7:4747`은 연결 거부 상태였고, S22는 ADB 장치로 정상
  인식됐지만 `Dozing` 및 잠금화면 상태여서 DroidCam 앱이 연결을 즉시 끊었다.
- 충돌 프로세스를 정리하고 S22를 깨운 뒤 DroidCam을 전면 실행하여 USB 연결을
  복구했다.
- `/camera2/image_raw/compressed` 실측 약 `20.4 FPS`, 컨베이어 ROI 주석 영상
  `/vision/conveyor/roi_image/compressed` 약 `20.1 FPS` 발행을 확인했다.
- 재실행 시 Wi-Fi와 USB 스크립트를 동시에 실행하지 않고 한 방식만 사용하며,
  S22 화면을 켜고 잠금 해제한 상태에서 DroidCam을 전면에 유지해야 한다.
- 장시간 실행 중 camera2와 ROI 프로세스는 CPU를 사용하면서도 ROS graph에서
  사라진 비정상 상태가 한 차례 발생했다. 두 ROS participant를 재시작한 뒤
  `/camera2/image_raw/compressed` 약 `22~26 FPS`, ROI 영상 약 `20 FPS`와 전체
  토픽 discovery가 정상 복구됐다.

### S22 USB 단일 실행 및 자동 복구 강화

- `run_camera2_usb.sh`를 단순 실행기에서 supervisor 방식으로 변경했다.
- S22 ADB serial 확인, 화면 깨우기, DroidCam 전면 실행, 잠금 확인, 기존
  Wi-Fi/USB writer 제거, ADB forward 초기화와 최대 5회 연결 재시도를 자동화했다.
- 실행 중 `droidcam-cli` 또는 ROS camera2 노드가 종료되면 두 프로세스를 함께
  정리하고 다시 연결하도록 했다. 실제 스트림 프로세스를 강제 종료한 시험에서
  자동 재연결 후 camera2와 ROI 약 `20 FPS` 복구를 확인했다.
- `~/KSMC/run_s22_conveyor.sh` 한 명령으로 camera2 프레임을 확인한 뒤 컨베이어
  ROI 노드까지 순서대로 실행하도록 통합했다.
- 재부팅 후 `/dev/video10` 자동 생성을 위한 v4l2loopback modules-load 및
  modprobe 설정 원본을 프로젝트에 추가했다.

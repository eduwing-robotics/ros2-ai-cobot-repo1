# 시스템 통합 작업 기록

## 최종 공정 목표

컨베이어 도착 감지 → 기판 위치/방향 인식 → FR5 부품 Pick 및 정밀 배치 →
조립 상태 검사 → PASS/FAIL 판정 → UI/로그 기록의 제조 셀을 구현한다.

카메라 역할:

- D435: Eye-in-Hand 정밀 위치 보정, 파지/배치, 필요 시 높이 확인
- Galaxy S22: 조립 스테이션 고정형 비전, 기판 도착·틀어짐 확인
- GoPro: 전체 셀 모니터링과 보조 안전 감시

현재 단계는 D435 Camera-to-Robot 좌표 정확도 확보이며 자동 Pick/조립은 아직
진행하지 않는다.
## 2026-08-12 — 최종 파지 좌표 전략 확정

- D435 RGB-D를 이용한 2단계 Eye-in-Hand visual servo 구조를 채택한다.
- 1단계: RGB fiducial/객체 검출 + aligned depth + 활성 Hand-Eye로 안전 높이까지
  거친 접근.
- 2단계: 가까운 거리에서 다시 RGB-D 검출하여 Camera-frame 잔차를 계산하고
  작은 XY/Z 보정만 수행.
- 단발 절대좌표의 1–2 mm 자세 의존 오차를 최종 배치까지 그대로 전달하지 않고,
  접근 후 재관측으로 상쇄한다.
- depth invalid, 좌표 jump, 시야 이탈 시 이동을 금지한다.
### RGB-D 물체 1차 안전 접근 검증

- 검정 테스트 물체를 depth 높이 범위로 분할하고 Camera XYZ→Base XY 변환,
  등록 부품 높이 10 mm와 ChArUco 기준면을 결합해 안전 접근점을 생성했다.
- 2단계 경로(안전 높이 수평 이동→저속 수직 접근)로 물체 윗면 100 mm 위까지
  실제 이동했으며 로봇 오류 및 충돌 신호 없이 목표에 도착했다.
### 첫 RGB-D Pick 성공

- ChArUco 작업대 기준 + aligned depth 물체 후보 분리 + 등록 높이 10 mm를
  결합해 100 mm 안전 접근점을 생성했다.
- 안전 접근 후 사용자 근접 확인으로 Tool XY 잔차를 보정하고, 열린 그리퍼로
  단계 하강하여 바닥 1~2 mm 여유에서 파지했다.
- 10 mm 시험 상승으로 물체 동반 상승을 확인했다. 이는
  `비전 검출 → Base 좌표변환 → 안전 접근 → 근접 보정 → 파지 확인` 전체 흐름의
  첫 실물 성공 사례다.
- 향후 자동화 대상: 물체 외곽/마스크 검출 안정화, 근접 XY 잔차 자동 계산,
  부품별 폭·높이·그리퍼 힘/속도 recipe, 파지 후 상승 및 실패 판정.
## 2026-08-12 — 반도체 모형 조립용 Vision MVP 방식 확정

- 렌더링 스크린샷에서 중앙 GPU, 양측 HBM, 긴 금색 부품, 소형 칩 및 수동소자
  구조를 확인했다.
- 짧은 일정에서는 YOLO 학습보다 `Fiducial board frame + CAD slot 좌표 +
  고대비 트레이 OpenCV contour/minAreaRect + aligned depth` 조합을 채택한다.
- 검은 부품과 검은 기판을 직접 색상 분할하지 않고 밝은 Pick 트레이를 사용한다.
- 상세 계획: `docs/VISION_ASSEMBLY_MVP_PLAN.md`.

### 조립 대상 정정

- 자동 조립 대상은 총 25개로 확정했다: 왼쪽 검정 사각형 5, 우측 흰색+갈색
  소형 5, 우측 하단 흰색+검정 표시 2, 긴 노랑/주황 부품 4, GPU 1, HBM 8.
- 작은 노란 소자는 기판에 붙은 상태로 일체 출력되므로 Pick/Place 대상에서
  제외한다.
- 25개를 6개 part recipe와 25개 board slot으로 모델링한다.

### 기판 기준점 방식 변경

- 기판에 ArUco를 영구 부착할 필요는 없으며 렌더링에 있는 빨간 링/체결 구멍
  중심을 CAD vision datum으로 사용하기로 했다.
- 4개 이상 링 중심을 contour/ellipse fitting으로 검출하고 CAD 패턴과 매칭해
  board X/Y/yaw 또는 planar pose를 계산한다.
- 대칭 방향 혼동 방지를 위해 한 링에 다른 색·지름·notch를 추가하는 것을
  3D 출력 설계에 권장한다. ArUco는 개발·복구용 fallback으로 유지한다.
- 링 설계를 바꿀 수 없을 때는 구멍 CAD 패턴으로 pose를 구한 뒤, 기판에 일체
  출력되는 비대칭 노란 소자 군집/배선의 template matching으로 0°/180° 방향을
  판별한다. 판별 신뢰도가 낮으면 자동 조립을 금지한다.

## 2026-08-12 — Unity/OBJ 조립 모델 좌표 추출

- 전달받은 `Board_obj`의 `ITEAM.prefab` 복제 위치·회전과 OBJ bounds를 함께
  해석하는 추출 도구를 추가했다.
- Unity X/Z를 기판 평면으로, root scale `0.01`을 `10 mm/model unit`으로
  변환해 기판 중심 기준 슬롯 후보 좌표를 JSON/CSV/SVG로 생성했다.
- 기판 크기 후보는 `140.00 × 110.34 mm`, 독립 조립 부품은 24개로 확인됐다.
- 요구 수량 25개와 비교했을 때 흰색+갈색 `cap_small`이 5개가 아니라 4개만
  존재한다. 누락 좌표를 추정값으로 활성화하지 않고 수정 조립 파일을 기다린다.
- NVIDIA, SK hynix, cap, board 등의 PNG와 Unity Material이 포함돼 있어 Unity
  외형은 제공된 렌더 사진과 유사하게 구성할 수 있다.
- 기판 OBJ의 수직 ray/표면 높이를 슬롯 내부와 주변에서 검사했으며 개별 칩
  포켓은 없었다. 외곽 placement 표면은 한 평면, GPU/HBM 영역은 그보다 약
  `2 mm` 높은 넓은 평면이다. 물리적 정렬 홈은 CAD 수정 항목으로 남겼다.
- 변경 파일: `vision_assembly/tools/extract_unity_board_layout.py`,
  `vision_assembly/config/board_layout_from_unity.{json,csv,svg}`.

## 2026-08-12 — 3대 카메라 기반 조립·검사 흐름 확정

- S22의 영상 ROI를 `pre-stop 감속 → stop 정지` 두 단계로 사용해 별도 광전
  센서가 없는 TurtleBot 컨베이어의 정지 오버슈트를 줄인다.
- 조립 중 정밀 좌표는 D435, 조립 완료 전체 전수검사는 S22, 전체 공정과 보조
  안전 감시는 GoPro로 역할을 분리한다.
- 최종 검사는 FR5가 시야 밖 자세로 이동한 뒤 수행하고, S22가 FAIL/불확실로
  표시한 slot만 D435가 근접 재검사한다.
- 내부 전기 불량은 영상으로 판정할 수 없으며 현재 범위는 누락, 위치, 방향,
  종류, 외관, 들뜸/높이 불량이다.

### 고정형 S22와 Eye-in-Hand D435 좌표 융합

- S22를 검사 전용으로 제한하지 않고 별도의 Eye-to-Hand extrinsic을 구축해
  조립 스테이션의 board/slot Base XY·yaw 좌표 공급원으로 사용한다.
- D435는 Pick 3D와 근접/depth, S22는 전역 평면 좌표를 담당한다. 양쪽 결과를
  동일 Base frame으로 변환한 뒤 consistency gate를 통과한 경우에만 접근한다.
- 근접 시 D435가 목표를 놓치면 마지막 유효 측정을 저장하고 S22가 제공하는
  slot 좌표 및 board Z에 따라 마지막 짧은 하강만 수행한다.

### S22 board snapshot 기반 무재관측 Place 모드

- FR5가 D435로 전체 트레이를 관측하는 대기 자세에 있고, S22가 기판 도착·정지
  후 `T_base_board`와 모든 Base slot 좌표를 먼저 확정하는 빠른 공정을 채택할
  수 있다.
- 이후 D435는 Pick에 사용하고, Place는 저장된 S22/CAD Base 좌표로 수행해
  D435가 기판을 다시 보지 않아도 된다. 시스템 분류는 D435 Eye-in-Hand + S22
  Eye-to-Hand의 hybrid 구조다.
- 이 모드는 기판 정지, S22 Eye-to-Hand 오차, CAD slot, TCP, grasp yaw/center,
  part height가 모두 허용 범위 내일 때만 사용한다. Place는 안전 높이 접근 후
  저속 수직 하강하고, 로봇 후퇴 후 S22가 결과를 검사한다.

## 2026-08-12 — S22 기반 TurtleBot 컨베이어 ROS 제어 설계

- 실물 영상과 모델링 이미지에서 TurtleBot 구동륜이 컨베이어 롤러를 직접
  회전시키는 구조를 확인했다. 기존 TurtleBot ROS 속도 명령을 컨베이어 모터
  명령으로 재사용할 수 있다.
- S22 검출을 `RUN_FAST → PRESTOP → ALIGN → HOLD_STOP → ASSEMBLY_READY` 상태
  머신과 연결한다. 한 번에 정지시키지 않고 영상 오차 기반 감속과 미세정렬을
  사용한다.
- stopper가 없어 정지점 반복도가 낮아도, 정지 후 S22가 실제 `T_base_board`를
  다시 계산하므로 FR5 작업영역 안에서 완전히 멈추면 조립 좌표를 보정할 수 있다.
- FR5가 조립 구역에 있을 때는 0 속도 interlock을 유지하고, 영상/DDS timeout과
  node 오류도 watchdog으로 정지시킨다.
- 상세 설계: `docs/CONVEYOR_VISION_ROS_ARCHITECTURE.md`.

## 2026-08-12 — 팀 하드웨어·소프트웨어 목표 아키텍처 정리

- FR5/PGEA/D435, S22, TurtleBot 컨베이어, GoPro, ROS 2 통합 노트북과
  Unity GUI/DT를 하나의 제조 셀 구성도로 정리했다.
- 복잡한 계층도 대신 `GUI/DT`, `Main Server`, `AI Server/Vision`, `FR5`,
  `Conveyor`의 5개 서브시스템으로 단순화했다.
- Main Server만 허브로 사용하고 네 개의 직접 연결만 표시해 선 교차와 중복
  정보를 제거했다. AI/Vision은 논리 블록이며 Main Server PC와 통합 가능하다.
- 발표·포트폴리오용 16:9 SVG/PNG와 간결한 설명 문서는
  `docs/architecture/`에 보관한다.

## 2026-08-13 — AI/Vision 서버 연결 경계 구현

- Main Server가 카메라 영상에 직접 종속되지 않도록 AI/Vision 측에서
  `/vision/detections`, `/vision/inspection`, `/vision/status` 인터페이스를
  제공한다.
- D435/S22/GoPro 입력을 `camera_manager`에서 논리 토픽으로 정리하고,
  검출과 검사는 별도 노드로 분리했다. Main Server와 같은 노트북에서 실행해도
  소프트웨어 경계는 유지된다.
- 상세 구현·검증 기록: `docs/logs/vision.md`.

## 2026-08-13 — ROS 2 노드·토픽·서비스 이름 명세 확정

- 팀명 접두사와 과도한 약어를 사용하지 않고 기능별 namespace와 설명적인
  snake_case 이름을 사용하는 원칙을 확정했다.
- Camera, AI/Vision, Main Server, FR5, Conveyor, GUI/DT, Calibration을 분야별로
  나누고 각 노드·토픽·서비스에 `구현 완료`, `기존 인터페이스`, `구현 예정`,
  `현장 확인 필요` 상태를 표시했다.
- Main Server는 아직 미구현임을 명시하고 `process_manager`, `safety_monitor`,
  `result_logger`와 `/process/*` 인터페이스를 구현 표준안으로 정리했다.
- Google Docs: [ROS 2 노드·토픽·서비스 명세서](https://docs.google.com/document/d/1z3BdkmYlqqxtZNj4pmafprMxciteMIoCzVRolI7dB1I/edit)
## 2026-08-17 — S22 정지 트리거와 TurtleBot 저속 제어 연결 준비

- `vision_server/conveyor_controller.py`를 추가해 S22의
  `/vision/conveyor/stop_trigger`를 TurtleBot `/cmd_vel` 정지로 연결하는 별도
  시험 제어 노드를 구현했다.
- 실제 이동은 `--execute --confirm-motion` 두 플래그가 모두 있을 때만 허용하며,
  시험 속도는 최대 `0.05 m/s`, 기본값은 `0.02 m/s`로 제한했다.
- 비전 heartbeat 1초 단절, 정지 트리거, 최대 30초 이내 사용자 지정 timeout,
  Ctrl+C 중 하나가 발생하면 Twist 0을 10회 발행하도록 했다.
- 실행 스크립트는 `ros2_ws/run_conveyor_stop_test.sh`이며 빌드와 기존 테스트
  `11 passed`, 플래그 없는 dry-run에서 무동작 종료를 확인했다.
- TurtleBot 주소는 `192.168.0.101`, 장치 이름은 `musk`로 확인했으나 SSH 인증이
  없어 원격 bringup과 실제 `/cmd_vel` 타입은 아직 확인하지 못했다. ROS domain 5
  등 확인한 로컬 도메인들에서도 TurtleBot 토픽은 발견되지 않아, 전원뿐 아니라
  TurtleBot bringup 실행과 동일 ROS domain 설정이 다음 선행 조건이다.
- 이후 사용자가 TurtleBot에서 Jazzy, `ROS_DOMAIN_ID=5`, burger bringup을 실행해
  `/cmd_vel`이 `geometry_msgs/msg/TwistStamped`이고 구독자가 `turtlebot3_node`
  하나임을 확인했다. 제어 노드 기본 메시지를 이에 맞게 수정하고 속도 0 명령의
  subscriber 연결도 검증했다.
- 기판을 정지선보다 30 px 이상 상류로 5프레임 이동하면 기존 stop latch를 자동
  해제하도록 재무장 조건을 추가해 반복 기능 시험이 가능하게 했다.
- 실제 기능 시험 요구에 맞춰 최대 시험 속도를 `0.10 m/s`로 조정했으며,
  `--timeout 0`에서는 시간 제한 없이 구동하되 비전 heartbeat 단절, 정지 trigger,
  Ctrl+C 안전 정지는 계속 유지하도록 했다.
- TurtleBot bringup 상태에서 `0.10 m/s`, timeout 비활성 조건으로 실구동했다.
  S22에서 기판 후단의 초록 정지선 통과를 감지하자 `vision stop trigger`가 발생했고,
  제어 노드가 속도 0을 10회 발행해 자동 정지까지 완료했다.
- 첫 heartbeat 수신 전 오정지를 막기 위해 시작 시 최대 3초간 속도 0으로 대기하는
  초기화 구간을 추가했고, 종료된 ROS context에 중복 정지 명령을 보내던 종료
  traceback도 방지했다.
- 긴 ROS 옵션을 매번 입력하지 않도록 프로젝트 루트에
  `run_conveyor_auto_stop.sh`를 추가했다. 파일 상단에 TurtleBot bringup, S22
  실행, 기판 배치, 자동 정지 및 Ctrl+C 사용 순서를 주석으로 기록했다.

## 2026-08-17 — 다른 개발 PC 이관 및 Git 배포 준비

- 절대 경로와 PC별 장치 설정을 공통 환경 파일로 분리하고, 저장소에는
  `config/ksmc.env.example`만 포함하도록 정리했다.
- 새 PC용 `scripts/setup_new_computer.sh`, 전체 빌드용 `scripts/build_all.sh`,
  상태 점검용 `scripts/doctor.sh`를 추가했다.
- 다음 작업자가 프로젝트 구조와 안전 조건을 바로 이해할 수 있도록
  루트의 `CODEX_HANDOFF.md`에 장비 구성, 실행 순서, 검증 상태와 남은 작업을
  기록했다.
- DroidCam 외부 소스는 저장소에 복제하지 않고 공식 저장소의 검증된 커밋
  `cdc044bd74873c6b8750750aac42db8029dac5c1`을 설치 시 내려받도록 고정했다.
- 배포 브랜치 이름은 기능 범위를 나타내는
  `vision-robot-conveyor-control`로 정했다.
- 배포 전 ROS 패키지 빌드, Python 문법 검사, shell 문법 검사, pytest 11개와
  시스템 doctor 검사를 통과했다.

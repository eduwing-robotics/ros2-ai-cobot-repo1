# FR5 Robot Control

FAIRINO FR5, PGEA-100-40 gripper, gripper-mounted RealSense D435 and ROS 2
Jazzy를 한 곳에서 개발하기 위한 통합 작업 폴더다.

이 프로젝트의 기준 구현은 이 디렉터리다. 원본
`ros2-ai-cobot-repo1`과 `FR5_AIR_DEMO_20260817`은 이관 근거로만 보존하며,
새 기능은 이 폴더에서 개발한다.

## 목표 제어 흐름

```text
D435 RGB + aligned depth + 현재 FR5 flange pose
  -> Camera 좌표의 부품/슬롯 관측
  -> Hand-Eye(T_flange_camera)로 Base 좌표 변환
  -> freshness/workspace/offset 검증
  -> dry-run pick/place plan
  -> 단일 motion executor를 통한 FR5 실행
  -> hover에서 재관측 후 제한된 폐루프 보정
```

카메라는 Eye-in-Hand 구조다. 영상 픽셀을 바로 로봇 명령으로 사용하지 않는다.
항상 다음 변환을 사용한다.

```text
T_base_target = T_base_flange @ T_flange_camera @ T_camera_target
```

## 디렉터리

- `robot_ws/`: FAIRINO 벤더 ROS 2 드라이버와 명령 서버
- `ros2_ws/src/vision_interfaces`: 비전 메시지 정의
- `ros2_ws/src/vision_server`: 카메라·검출·aligned depth 처리
- `ros2_ws/src/fr5_process_sequences`: 안전조건을 검사하는 dry-run 플래너
- `calibration/`: D435/ChArUco/Hand-Eye 코드와 활성 보정값
- `vision_assembly/`: 부품·기판·슬롯 검출 및 기존 단계별 이동 실험
- `teach_points/`: 공중 시험용 provisional 교시점
- `references/`: 로봇 제어 아키텍처와 commissioning 기준
- `docs/MIGRATION.md`: 두 원본에서 가져온 범위와 제외 항목

## 최초 설정과 빌드

```bash
cd /home/juchan-yoon/FR5_robot_control
cp config/ksmc.env.example config/ksmc.env
./scripts/build_all.sh
./scripts/doctor.sh
./scripts/test_all.sh
```

`config/ksmc.env`는 장비별 값이므로 Git에 넣지 않는다.

## 조립 스택 통합 실행

여러 터미널에서 카메라·FAIRINO·Unity Endpoint·비전 노드를 따로 띄우지 않고
다음 한 명령으로 관리한다.

```bash
./run_fr5_assembly_stack.sh start
./run_fr5_assembly_stack.sh check
./run_fr5_assembly_stack.sh view
./run_fr5_assembly_stack.sh restart
./run_fr5_assembly_stack.sh clean
```

이 실행기는 로봇 이동 명령을 보내지 않는다. 중복 프로세스 종료 정책, 카메라
프로필, 상태 및 로그 명령은 [통합 실행 명령](docs/FR5_ASSEMBLY_STACK_COMMANDS.md)을
참고한다.

## 안전한 개발 순서

1. D435 RGB-D와 CameraInfo 토픽만 확인한다.
2. FR5 상태를 읽기 전용으로 확인한다.
3. 부품 검출과 Camera→Base 변환을 로봇 이동 없이 검증한다.
4. `fr5_process_sequences`로 전체 경로를 dry-run 검증한다.
5. 작업자가 확인한 뒤 10% 이하 속도로 관측 자세→hover만 시험한다.
6. hover 재관측의 반복성이 확인된 뒤 짧은 보정과 수직 하강을 별도 승인한다.

기존 `vision_assembly/scripts/full_pick_to_board_hover.py`는 실험 이력으로
포함되어 있지만 실제 실행 전용이며 기본 속도와 target freshness 정책이 최종
안전 기준에 맞지 않는다. 통합 motion executor가 완성되기 전 자동운전에
사용하지 않는다.

## 현재 구현과 검증

- `run_fr5_cycle.sh`는 새 기판/트레이 촬영, 일반20개 조립, SMD5개 근접측정/조립을 연결한다. 사용법과 실행 전 조건은 [단일 런처 문서](docs/FR5_CYCLE_LAUNCHER_KO.md)를 확인한다.
- 성공 파지·배치 방향, 최신 SMD 배치높이, 촬영 최신성 및 관절 경로 제한을 계획과 실행에서 검사한다. 조립 동작 완료와 실제 안착 품질은 별도로 기록한다.
- Unity 로봇 API·Ghost 미리보기·보드/트레이 캘리브레이션 API가 있다. Real API 하드웨어 실행은 기본 비활성이다.
- `run_fr5_assembly_stack.sh view`는 D435 RQT와 USB 휴대폰 검사 화면을 함께 연다. 휴대폰의 mm 추정과 전체25개 안착 검증은 별도 검증 과제다.
- 최근 문제 분석·검증 범위는 [프로젝트 검토](docs/PROJECT_REVIEW_2026-09-08.md)와 [결함 수정 기록](docs/PROJECT_REVIEW_FIXES_2026-09-08.md), 현장 상태는 [최신 인계](docs/CODEX_HANDOFF.md)와 [작업일지](작업일지/README.md)를 확인한다.

`./scripts/test_all.sh`는 ROS 개발 환경을 읽어 메시지 타입을 사용할 수 있게 하고, 조립·비전·API·스택·진행률의 오프라인 시험과 구문 검사를 실행한다. 실제 ROS 서비스와 로봇·GUI 실행 경계는 시험에서 대체한다. 시스템 Python에 pytest가 필요하며, 카메라나 로봇을 연결할 필요는 없다. 전체25개 반복 실기와 슬롯별 품질 판정은 이 시험과 별도로 검증한다.


## 2026-09-08 소스 배포 상태

최신 작업과 다음 시작점은 [오늘 작업일지](작업일지/2026-09-08.md)를 먼저 확인한다. 로봇 API·그리퍼 피드백·런처와 높은 위치 연속 이동을 포함한다. 연속 이동은 [적용 범위와 검증 상태](docs/CONTINUOUS_TRANSFER_20260908.md)를 따른다. 카메라 이동 경로는 별도 개선 예정이며 마지막 실행은 VRM3 검출 품질 미달로 중단됐다.

빌드/install/log/cache 및 현장 runtime은 Git에서 제외하고 재생성한다. 실행 기준 설정과 작은 회귀시험 fixture는 포함한다. 대형 모델/영상과 전체 checkpoint 복제본, Unity 전달 ZIP, 일회성 진단 산출물은 별도 현장 보관이다. 로컬 config/ksmc.env의 KSMC_REAL_HARDWARE_EXECUTION 및 KSMC_CONTINUOUS_TRANSFER는 장비별 명시 설정이며 배포 예제 기본값은 false다.

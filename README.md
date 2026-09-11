# HBM 조립체 디지털 트윈

Unity, ROS 2, 로봇 설비와 생산 데이터를 연결해 생산 요청, 조립, 검사와 결과 확인을 하나의 흐름으로 제공하는 작업 공간입니다.

Mock과 Real은 MainServer와 AssemblySequencer를 각각 독립 프로세스로 실행합니다. Real AssemblySequencer는 장비의 공개 ROS API를 사용하며 MoveIt과 `ros2_control`을 실행하지 않습니다.

시스템은 `요청·표현 → 업무·조정 → 실행·설비`의 세 계층으로 구성합니다. 전송 브리지와 production 데이터 계약은 이 계층을 연결하는 기반이며 별도 업무 계층이 아닙니다.

## 저장소 소유권

| 경로 | 소유 책임 |
|---|---|
| `UnityDT/` | 작업자 화면, Scene, 디지털 트윈 표현, Scenario와 backend 선택 |
| `MAIN_SERVER/` | 외부 요청 검증, 생산 조회, Job 등록과 품질 문서 생성 |
| `ASSEMBLY_SEQUENCER/` | Job·Unit 상태 전이, 레시피 검증과 조립·검사 순서 조정 |
| `Farino_AIO_Mock/` | FR5 실행 구성, Real·Mock backend와 Mock 통합 실행 |
| `Ros2UnityEndopoint_PKG/` | Unity와 ROS 2 사이의 메시지 전송 |
| `DATA_STATION/DB/` | MainServer와 Sequencer가 공유하는 PostgreSQL 스키마·제약·권한 |
| `docs/` | 시스템 설계, 공개 API 목차와 과거 기록 |
| `launch/` | MainServer·AssemblySequencer의 Mock/Real 공개 실행 진입점 |

`build/`, `install/`, `log/`, Unity `Library/`와 `Trash/`는 생성물 또는 로컬 격리 공간이며 기준 원본을 두지 않습니다.

## 기준 문서

- 프로젝트 작업 정책: [AGENTS.md](AGENTS.md)
- 문서 안내: [docs/index.md](docs/index.md)
- 시스템 설계: [docs/architecture/index.md](docs/architecture/index.md)
- 공개 API 목록: [docs/API.md](docs/API.md)
- production 데이터 설계: [DATA_STATION/DB/README.md](DATA_STATION/DB/README.md)

컴포넌트별 역할은 해당 README, 구체 endpoint와 payload는 제공 컴포넌트의 API 문서가 소유합니다. 실행 절차와 공개 명령은 아래 절만을 기준으로 사용합니다.

`reports/`와 `archive/`는 시점별 조사·과거 판단 기록이며 현재 설계 계약으로 사용하지 않습니다.

## 실행

모든 명령은 저장소 최상단에서 실행합니다. MainServer와 AssemblySequencer는 같은 모드를 선택해 터미널 두 개에서 각각 실행합니다. Mock은 ROS domain 42, Real은 domain 5를 런치 내부에서 고정합니다.

최초 실행 또는 소스 변경 뒤에는 다음 workspace를 빌드하고 현재 셸에 적용합니다.

```bash
cd ASSEMBLY_SEQUENCER
colcon build --symlink-install
source install/setup.bash
cd ../Farino_AIO_Mock
colcon build --symlink-install
source install/setup.bash
cd ..
```

Mock 실행 전 `MAIN_SERVER_DB_DSN`에는 `job_submitter` 권한 계정, `PRODUCTION_DB_DSN`에는 `production_writer` 권한 계정의 Mock DB 접속 문자열을 설정합니다.

```bash
ros2 launch launch/main_mock.launch.py
ros2 launch launch/assembly_mock.launch.py
```

Real 실행 전 같은 두 DSN을 Real 전용 DB로 설정하고, AssemblySequencer 프로세스 환경에 `VISION_BASE_URL`, `KSMC_VISION_API_TOKEN`, `DEFECT_IMAGE_ROOT`를 설정합니다. DB의 관리자 설정 `app.runtime_mode`도 `real`이어야 합니다.

```bash
ros2 launch launch/main_real.launch.py
ros2 launch launch/assembly_real.launch.py
```

Real Assembly 런치는 ROS TCP Endpoint와 AssemblySequencer만 시작합니다. 장비 측 `main` 서버, 컨베이어 서버와 Vision 서버는 각 설비 PC에서 먼저 실행되어 `/real/*`, `/conveyor/*`와 검사 HTTP API를 제공해야 합니다. Endpoint가 이미 실행 중이면 `start_endpoint:=false`를 추가할 수 있습니다.

# HBM 조립체 디지털 트윈 · `Main_Server&DT` 브랜치

KSMC 스마트 제조 셀에서 **작업자 화면(Unity 디지털 트윈)과 생산 서버**를 담당하는 브랜치입니다.
생산 요청을 Job으로 등록하고, 로봇·컨베이어·비전 설비에 조립·검사 순서를 지시한 뒤 결과를 DB와 화면에 보여 줍니다.
Mock 모드로는 실제 설비 없이 전체 흐름을 실행할 수 있습니다.

## 브랜치 구성

| 브랜치 | 담당 |
|---|---|
| `Main_Server&DT` (현재) | Unity DT, MainServer, AssemblySequencer, 공유 DB 스키마, FR5 Mock |
| `fr5-robot-control-full` | FR5 로봇·그리퍼·D435 실기 제어 |
| `codex/conveyor-cell-integration` | 컨베이어 제어와 기판 검사 ROS 서비스 |
| `main` | 통합 대상 |

Real 모드에서 이 브랜치는 설비 측이 제공하는 `/real/*`, `/conveyor/*`, `/vision/inspection/*` ROS 서비스를 호출합니다.

## 구성

| 경로 | 역할 |
|---|---|
| `UnityDT/` | 작업자 화면, 디지털 트윈 표현, Scenario와 backend 선택 |
| `MAIN_SERVER/` | 외부 요청 검증, 생산 조회, Job 등록과 불량대책서 생성 |
| `ASSEMBLY_SEQUENCER/` | Job·Unit 상태 전이, 레시피 검증과 조립·검사 순서 조정 |
| `Farino_AIO_Mock/` | FR5 실행 구성과 Mock 통합 실행 |
| `Ros2UnityEndopoint_PKG/` | Unity ↔ ROS 2 메시지 전송 |
| `DATA_STATION/DB/` | MainServer와 Sequencer가 공유하는 PostgreSQL 스키마·권한 |
| `docs/architecture/` | 세 계층 책임, 생산 불변 조건과 완료·실패 경계 |
| `launch/` | MainServer·AssemblySequencer의 Mock/Real 실행 진입점 |

시스템은 `요청·표현(UnityDT, MainServer) → 업무·조정(AssemblySequencer) → 실행·설비(로봇·비전·컨베이어)` 세 계층으로 나뉩니다.
자세한 내용은 [시스템 아키텍처](docs/architecture/index.md)를 참고하세요.

## 실행

Ubuntu 24.04 + ROS 2 Jazzy 환경에서 저장소 최상단 기준으로 실행합니다.

```bash
bash install_Server.sh
```

설치기는 apt·rosdep 의존성을 설치하고 Endpoint → 로봇 workspace → Sequencer 순으로 빌드한 뒤, 모드별 DB 접속 문자열과 이미지 경로를 한 번 입력받아 Git에서 제외되는 `launch/.env.mock`·`launch/.env.real`(권한 600)에 저장합니다.
새 터미널을 열고 MainServer와 AssemblySequencer를 같은 모드로 각각 실행합니다.

```bash
# Mock (ROS domain 42)
ros2 launch launch/main_mock.launch.py
ros2 launch launch/assembly_mock.launch.py

# Real (ROS domain 5)
ros2 launch launch/main_real.launch.py
ros2 launch launch/assembly_real.launch.py
```

- DB 서버·스키마·로그인 계정은 미리 준비해야 합니다. 설치기는 DB 생성·권한 변경·migration을 하지 않습니다([DB 설계](DATA_STATION/DB/README.md)).
- `MAIN_SERVER_DB_DSN`은 `job_submitter`, `PRODUCTION_DB_DSN`은 `production_writer` 역할을 가진 서로 다른 LOGIN 계정이며, 같은 DB의 `app.runtime_mode`가 모드와 일치해야 합니다.
- Real은 설비 PC의 서비스가 먼저 실행되어 있어야 합니다. Endpoint가 이미 떠 있으면 `start_endpoint:=false`를 붙입니다.
- 옵션: `--mode mock|real`(대상 한정), `--configure-only`(설정만), `--check`(읽기 전용 검증), `--skip-deps`(소스 수정 후 재빌드).
- 비대화형 설치는 `MOCK_*`/`REAL_*` 접두사 환경 변수(`MAIN_SERVER_DB_DSN`, `PRODUCTION_DB_DSN`, `DEFECT_IMAGE_ROOT`)로 값을 전달합니다.
- 비밀번호나 토큰은 Git·문서·명령 인자에 기록하지 않습니다.

## 공개 API

| 제공자 | 공개 경계 | 소비자 | 상세 계약 |
|---|---|---|---|
| MainServer | HTTP `/api/v1/*` | UnityDT·외부 클라이언트 | [MAIN_SERVER/Main_serverAPI.md](MAIN_SERVER/Main_serverAPI.md) |
| Assembly Sequencer | ROS 2 service·topic | UnityDT·MainServer | [ASSEMBLY_SEQUENCER/API.md](ASSEMBLY_SEQUENCER/API.md) |

Real 조립은 등록된 Job의 시작 요청으로 컨베이어 조립 위치 이동 → 로봇 조립 → 컨베이어 검사 위치 이동 → 검사 순서로 진행되며, 요청 수락은 완료를 뜻하지 않습니다.
Real 검사 타입은 `ASSEMBLY_SEQUENCER/src/vision_interfaces`에 포함되어 함께 빌드됩니다.

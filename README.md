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

Ubuntu 24.04와 ROS 2 Jazzy apt 저장소가 준비된 PC에서 최초 설치는 다음 한 명령으로 수행합니다. 일반 사용자로 실행하며 OS 패키지 설치에만 `sudo`를 사용합니다.

```bash
bash install.sh
```

설치기는 기존 Python/ROS 의존성을 apt·rosdep으로 설치하고 Endpoint → 로봇 workspace → Sequencer 순으로 빌드합니다. Mock과 Real의 DB 접속 문자열과 공유 이미지 경로를 최초 한 번 입력받습니다. 비밀 입력은 화면에 표시하지 않습니다. DB 서버·스키마·로그인 계정은 사전에 준비해야 하며, 기존 DB 생성·권한 변경·migration을 자동으로 수행하지 않습니다.

`MAIN_SERVER_DB_DSN`은 `job_submitter`, `PRODUCTION_DB_DSN`은 `production_writer` 역할을 부여받은 서로 다른 일반 LOGIN 계정의 PostgreSQL 접속 문자열입니다. 두 역할 자체는 NOLOGIN이므로 접속 사용자로 쓸 수 없습니다. 같은 모드의 두 계정은 같은 DB에 연결해야 하고, DB 관리자 설정 `app.runtime_mode`는 각각 `mock`·`real`이어야 합니다. 과거 `TPJT_POSTGRES_DSN`은 자동 전용하지 않습니다.

검증된 설정은 Git에서 제외되는 `launch/.env.mock`과 `launch/.env.real`에 JSON으로 저장하며 파일 권한은 `600`입니다. `DEFECT_IMAGE_ROOT`는 양쪽 서버가 함께 사용하는 기존 절대경로입니다. Real 검사는 ROS domain 5의 `/vision/inspection/*` 서비스를 사용하며 HTTP 주소·토큰을 사용하지 않습니다. 설치기는 DB 모드·역할·스키마 존재와 로컬 경로를 확인하지만 원격 장비 준비 완료까지 보장하지는 않습니다.

설치 완료 후 새 Bash 터미널을 열면 `~/.bashrc`에 등록한 ROS workspace가 적용됩니다. 이후 별도 `export` 없이 아래 네 공개 런치를 사용합니다. 우선순위는 기존 DB 런치 인자 → 명시적으로 설정한 프로세스 환경 변수 → 모드별 로컬 설정입니다. 기존 터미널에 남은 DSN은 로컬 설정보다 우선하므로 모드를 바꿀 때 주의합니다.

Mock:

```bash
ros2 launch launch/main_mock.launch.py
ros2 launch launch/assembly_mock.launch.py
```

Real:

```bash
ros2 launch launch/main_real.launch.py
ros2 launch launch/assembly_real.launch.py
```

Real Assembly 런치는 ROS TCP Endpoint와 AssemblySequencer만 시작합니다. 장비 측 `main` 서버, 컨베이어 서버와 Vision 서버는 각 설비 PC에서 먼저 실행되어 `/real/*`, `/conveyor/*`와 `/vision/inspection/*` ROS 서비스를 제공해야 합니다. Endpoint가 이미 실행 중이면 `start_endpoint:=false`를 추가할 수 있습니다.

설치기 재실행은 기존 설정을 유지합니다. 필요한 경우 `--mode real` 또는 `--mode mock`으로 설정 대상을 좁힐 수 있습니다. `--configure-only`는 패키지 설치·빌드를 생략하고 설정만 검증·저장하며, `--check`는 DB 읽기 전용 검증만 수행하고 파일을 변경하지 않습니다. 소스 수정 뒤에는 `bash install.sh --skip-deps`로 다시 빌드합니다. ROS 환경만 수동으로 적용해야 하는 셸에서는 `/opt/ros/jazzy/setup.bash`, `Ros2UnityEndopoint_PKG/install/local_setup.bash`, `Farino_AIO_Mock/install/local_setup.bash`, `ASSEMBLY_SEQUENCER/install/local_setup.bash` 순서로 source합니다.

설정 교체나 비대화형 설치에서는 `REAL_MAIN_SERVER_DB_DSN`, `REAL_PRODUCTION_DB_DSN`, `REAL_DEFECT_IMAGE_ROOT`을 설치 프로세스 환경에 전달합니다. Mock은 `MOCK_MAIN_SERVER_DB_DSN`, `MOCK_PRODUCTION_DB_DSN`, `MOCK_DEFECT_IMAGE_ROOT`를 사용합니다. 이 접두사는 설치 입력에만 쓰며 네 런치는 저장된 설정에서 기존 환경 변수 이름을 사용합니다. 비밀번호나 토큰을 공유 문서·명령 인자·Git에 기록하지 않습니다.

Real 검사 서비스 타입은 `ASSEMBLY_SEQUENCER/src/vision_interfaces`에 포함되어 기존 빌드 순서로 함께 생성됩니다. 제공자 `eduwing-robotics/ros2-ai-cobot-repo1`의 `16979a2bf1e6206db043fd399b67656330b33200` 버전과 동일한 인터페이스를 양쪽 PC에서 사용합니다. 이전 로컬 설정에 남은 `VISION_BASE_URL`과 `KSMC_VISION_API_TOKEN` 항목은 제거해야 합니다. `DEFECT_IMAGE_ROOT`는 MainServer와 Sequencer의 실행·검사 증거 저장소로 유지합니다.

# HBM 조립체 디지털 트윈

Unity, ROS 2, 로봇 설비와 생산 데이터를 연결해 생산 요청, 조립, 검사와 결과 확인을 하나의 흐름으로 제공하는 작업 공간입니다.

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

`build/`, `install/`, `log/`, Unity `Library/`와 `Trash/`는 생성물 또는 로컬 격리 공간이며 기준 원본을 두지 않습니다.

## 기준 문서

- 프로젝트 작업 정책: [AGENTS.md](AGENTS.md)
- 문서 안내: [docs/index.md](docs/index.md)
- 시스템 설계: [docs/architecture/index.md](docs/architecture/index.md)
- 공개 API 목록: [docs/API.md](docs/API.md)
- production 데이터 설계: [DATA_STATION/DB/README.md](DATA_STATION/DB/README.md)

컴포넌트별 역할은 해당 README, 구체 endpoint와 payload는 제공 컴포넌트의 API 문서가 소유합니다. 설치·실행 절차는 해당 공개 진입점의 README만 따르며 Mock 전체 스택은 [Mock 올인원 실행](Farino_AIO_Mock/README.md#mock-올인원-실행)이 단일 기준입니다.

`reports/`와 `archive/`는 시점별 조사·과거 판단 기록이며 현재 설계 계약으로 사용하지 않습니다.

# HBM 조립체 디지털 트윈

Unity, ROS 2, 로봇 설비와 생산 데이터를 연결해 HBM 조립체의 요청, 조립, 검사와 품질 확인을 하나의 흐름으로 제공하는 작업 공간입니다.

이 저장소는 특정 프로세스 배치나 통신 기술보다 책임 경계를 우선합니다. 실행 명령과 인터페이스 식별자는 각 컴포넌트 문서와 소스가 소유하고, 이 문서는 시스템이 지켜야 할 설계만 설명합니다.

## 설계 원칙

- 시스템은 `요청·표현 → 업무·조정 → 실행·설비`의 세 계층으로 유지합니다.
- 각 계층은 인접한 하위 계층의 공개 계약만 사용합니다.
- 생산 요청은 클라이언트가 만든 `job_id`로 한 번만 등록하며 재시도는 새 Job을 만들지 않습니다.
- 목표 수량은 검사 PASS 수량입니다. 검사 FAIL은 생산 시도로 남지만 목표 수량에는 포함하지 않습니다.
- 실행 성공은 요청 수락이 아니라 실제 조립과 검사가 끝났음을 뜻합니다.
- 안전정지 중에는 실행 상태를 임의로 완료·실패 처리하지 않습니다.
- 재시작 후 불명확한 중간 동작을 이어서 실행하지 않습니다.
- 레시피 본문과 설비 좌표는 실행 계층이 소유하며 생산 DB에는 실행 사실만 남깁니다.

## 폴더별 소유권

| 폴더 | 소유 책임 |
|---|---|
| `UnityDT/` | 작업자 화면, Scene, 디지털 트윈 표시, Scenario와 Mock/Real 선택 |
| `MAIN_SERVER/` | 외부 요청 검증, 생산 조회, Job 등록과 품질 문서 생성 |
| `ASSEMBLY_SEQUENCER/` | Job·Unit 상태 전이, 레시피 검증, 조립·검사 순서와 결과 기록 |
| `Farino_AIO_Mock/` | FR5, MoveIt, Mock/Real 로봇 실행과 설비 연동 |
| `Ros2UnityEndopoint_PKG/` | Unity와 ROS 2 사이의 메시지 전송 |
| `DATA_STATION/` | 생산 데이터 스키마, 제약조건과 접근 권한 |
| `docs/` | 둘 이상의 컴포넌트에 걸친 시스템 설계, 통합 계약, 조사 기록과 과거 설계 |

생성물인 `build`, `install`, `log`, Unity `Library`와 로컬 격리 공간 `Trash`는 소유 문서나 기준 원본을 두는 위치가 아닙니다.

## 문서

- [프로젝트 설계 개요](docs/index.md)
- [시스템 아키텍처](docs/architecture/index.md)
- [계층 간 통합 계약](docs/API.md)
- [생산 데이터 설계](DATA_STATION/DB/README.md)
- [Unity UI 설계](UnityDT/Docs/UI.md)
- [Assembly Sequencer](ASSEMBLY_SEQUENCER/README.md)
- [MainServer](MAIN_SERVER/README.md)

세부 설치·실행 방법과 변경 가능한 식별자는 해당 컴포넌트 README와 소스를 따릅니다.

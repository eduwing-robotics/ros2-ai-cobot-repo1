# HBM 조립체 디지털 트윈 프로젝트 개요

이 문서는 레포 전체의 유일한 기능 목표 문서다. 현재 구현과 완성 목표를 구분하며, 구체 API는 기술 문서, 미구현 항목은 [TODO](TODO.md)에서 관리한다.

## 1. 기능 목표

HBM 조립체 패키지 보드를 대상으로 다음 흐름을 Mock과 Real에서 같은 업무 의미로 제공한다.

```text
제품·재고 확인 → 조립 요청 → 로봇 작업 → 검사 → 생산·불량 기록 → 품질 확인
```

Unity는 운전 화면과 디지털 트윈을 제공하고, ROS2/MoveIt 계층은 실제 작업 완료를 책임진다. MainServer는 HTTP 조회와 조립 요청 진입점을 제공하며, PostgreSQL은 확정된 생산·검사 사실을 보관한다.

## 2. 현재 제공 기능

### Unity 디지털 트윈

- FR5 모델, 관절·TCP·그리퍼 상태와 작업 셀을 표시한다.
- RUN, INSPECT, MANUAL, QUALITY 화면을 제공한다. SETUP 화면은 아직 없다.
- `RobotMaster` 한 곳에서 Mock/Real backend를 선택한다.
- Scenario는 주입된 `IRobotScenarioControl.ExecuteAsync()`만 호출한다.
- Mock 자동 조립은 서비스 수락이 아니라 `COMPLETED` callback을 받은 뒤에만 성공한다.
- Real 상태 수신과 저수준 수동 제어 경로는 일부 존재하지만 Real 자동 조립은 아직 지원하지 않는다.

### Mock 조립 실행

- Unity가 씬의 부품·슬롯 Transform으로 observation을 만들고 ROS2 `/unity/assembly/start` 서비스에 전달한다.
- Mock ROS 노드는 고정 레시피 1개, 수량 1개, 동시 작업 1건을 실행한다.
- `/unity/assembly/feedback`의 `STARTED`, `PICKED`, `PLACED`, `COMPLETED`, `FAILED`로 진행과 종료를 전달한다.
- 같은 서비스의 `status` 요청으로 ROS 메모리의 최근 작업 스냅샷을 조회한다.
- 선택적으로 `mock_db_bridge`를 사용하면 외부 계약을 유지하면서 Job·Unit·재고·검사 결과를 `production`에 기록한다.

### MainServer

- 제품, 슬롯·부품 구성, 재고 부족분, 작업·Unit, 슬롯별 불량률을 HTTP로 조회한다.
- `POST /api/v1/assemblies`가 받은 조립 JSON을 ROS2 `/unity/assembly/start`로 전달한다.
- `GET /api/v1/assemblies/current`가 같은 서비스의 상태 스냅샷을 조회한다.
- Mock/Real 모드는 API 경로를 바꾸지 않고 실행 설정만 선택한다.
- 현재 Unity 화면은 MainServer의 제품·작업·품질 조회 API와 완전히 연결되어 있지 않다.

구체 계약은 [MainServer HTTP API](MAIN_SERVER/Main_serverAPI.md)와 [Unity ↔ ROS2 API](UnityDT/Docs/API.md)를 따른다.

## 3. 현재 실행 흐름

### Unity에서 시작하는 Mock Scenario

```text
Scenario
  → 컨베이어를 조립 위치로 이동
  → 주입된 MockAssemblyScenarioControl.ExecuteAsync()
  → /unity/assembly/start
  → mock_sim 또는 mock_db_bridge
  → /unity/assembly/feedback
  → COMPLETED 후 검사 위치로 컨베이어 이동
```

`mock_db_bridge`를 사용하면 내부 Mock 실행 완료 후 재고 차감, 검사 기록과 Job 마감이 성공해야 외부 `COMPLETED`가 전달된다.

### MainServer에서 시작하는 조립

```text
HTTP POST /api/v1/assemblies
  → MainServer AssemblyGateway
  → /unity/assembly/start
  → 기존 Mock 조립 경로
```

MainServer와 Unity Mock은 현재 같은 ROS 서비스를 호출하지만 서로를 경유하지 않는다.

## 4. 책임 경계

### Unity

- 화면, 3D 상태와 사용자 조작을 담당한다.
- Scenario의 상위 작업 시점과 중단 여부를 결정한다.
- DB에 직접 접속하지 않는다.
- Mock/Real 통신 차이, ROS 응답 해석과 완료 판정을 Scenario나 UI에 두지 않는다.

### RobotMaster와 backend

- `RobotMaster`만 Mock/Real backend를 선택하고 Scenario와 수동 조작에 계약을 주입한다.
- `IRobotScenarioControl`은 자동 조립의 실제 완료·실패·타임아웃을 책임진다.
- `IRobotControl`은 작업 흐름 밖의 수동 조작만 책임진다.

### MainServer

- 읽기 전용 DB 조회와 HTTP 입력 검증을 담당한다.
- 현재 조립 실행 API에서는 ROS2 서비스 client를 직접 사용한다.
- Unity 오브젝트를 해석하거나 로봇 작업의 실제 완료를 스스로 판정하지 않는다.

### ROS2 조립 계층

- 레시피 검증, MoveIt 계획, 로봇·그리퍼 실행과 작업 완료를 책임진다.
- DB bridge를 사용할 때는 확정된 실행 결과와 재고 변경을 트랜잭션 경계에서 기록한다.
- Mock 가상 물체와 Real 비전·하드웨어 차이는 각 구현 내부에서 처리한다.

## 5. DB 핵심 설계

PostgreSQL 인스턴스 하나에 역할이 다른 세 스키마를 둔다.

| 스키마 | 책임 |
|---|---|
| `production` | 제품·슬롯·부품 현재고, Job, Unit, 검사와 불량 슬롯 |
| `part_catalog` | 제조사, 공급·대체 후보, 데이터시트와 검사 체크리스트 |
| `defect_report` | 품질 임계값, 알림, 고정 근거와 개선 결과 |

핵심 원칙은 다음과 같다.

- `production`에는 제품 한 대 단위의 확정 생산·검사 사실만 기록한다.
- 관절·TCP 스트림과 조립 스텝 진행은 영속 DB에 저장하지 않는다.
- 레시피 본문과 좌표는 파일과 Git이 소유하고 DB에는 `recipe_version`만 기록한다.
- 각 스키마는 자기 무결성을 책임지며 스키마 간에는 물리 외래키를 두지 않는다.
- 검사 불량은 실행 실패와 구분한다. 정상 종료된 Unit도 검사 결과는 FAIL일 수 있다.

상세 계약은 [production DB 설계](UnityDT/Docs/DB.md), [3개 스키마 설계](UnityDT/Docs/DB3.md), [DDL](DATA_STATION/DB/001_schema.sql), [레시피 규격](UnityDT/Docs/Recipe.md)을 기준으로 한다.

## 6. 완성 판정

다음 조건을 Mock과 Real에서 같은 의미로 만족하면 기능 목표가 완료된다.

1. 사용자가 제품과 수량을 확인하고 조립을 요청할 수 있다.
2. 선택된 backend가 안전 조건과 입력을 검증하고 조립·검사를 실제 완료한다.
3. Unity가 진행 상태, 3D 동작, 실패 원인과 검사 결과를 표시한다.
4. 완성품, 재고, 검사와 불량 위치가 일관되게 저장된다.
5. Real 자동 조립도 Mock과 같은 성공·실패·타임아웃 계약을 제공한다.
6. 품질 화면과 대책서는 저장된 근거 데이터를 사용한다.

구현 순서와 아직 필요한 결정은 [TODO](TODO.md)만 갱신한다.

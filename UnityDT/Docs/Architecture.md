# 현재 시스템 구조

이 문서는 현재 코드로 실행되는 Unity·MainServer·ROS2·DB 경계를 설명한다. HTTP 계약은 [MainServer API](../../MAIN_SERVER/Main_serverAPI.md), 조립 실행 계약은 [AssemblySequencer API](../../ASSEMBLY_SEQUENCER/API.md)를 따른다.

## 전체 구조

```text
Unity Scenario ── RobotMaster ── MockAssemblyScenarioControl
                                      ├─ HTTP Job metadata
                                      │        ▼
                                      │    MainServer ── INSERT ── production.jobs
                                      │
                                      └─ ROS job_id + Mock coordinates
                                               ▼
                                      AssemblySequencer Mock Node
                                      ├─ claim Job·create Unit ── production DB
                                      ├─ internal mock_sim ── MoveIt
                                      └─ DB Writer ── Unit·검사·재고·Job

Unity ←─ /unity/assembly/feedback ── AssemblySequencer
Unity·MainServer ── status ───────→ /unity/assembly/start
```

MainServer에는 제품·수량·레시피와 UUID `job_id`만 보낸다. Mock 좌표는 DB나
MainServer를 통과하지 않고 Unity가 AssemblySequencer에 직접 전달한다.
AssemblySequencer가 Job과 Unit 상태, YAML 작업 흐름과 실제 완료를 소유한다.

## Unity 조립 흐름

`RobotMaster`는 Mock/Real backend를 선택하는 유일한 위치다.

```text
RobotMaster
  ├─ Scenario에 IRobotScenarioControl 주입
  └─ 선택 backend의 상태와 IRobotControl 노출

Scenario
  → IRobotScenarioControl.ExecuteAsync()
```

Scenario는 좌표, ROS 메시지, Mock/Real 분기와 완료 callback을 해석하지 않는다.
선택된 backend의 `ExecuteAsync()`가 입력 검증, 통신, 완성 PCB 이송, 실제 완료,
실패와 timeout을 책임진다.

## Unity 핵심 스크립트 책임

| 소유자 | 현재 책임 |
|---|---|
| `RobotMaster` | Mock/Real backend 선택·초기화와 Scenario·상태·제어 계약 노출 |
| `Scenario` | 조립 요청의 상위 진입점 |
| `MockAssemblyScenarioControl` | Job 생성, Mock 좌표 전달, 상태 복구, feedback 완료 판정과 씬 반영 |
| `MockRobotControl` | Mock 수동·저수준 ROS 명령과 명령 완료 판정 |
| `RealAssemblyScenarioControl` | Real 자동 조립 계약 경계. 현재는 미지원 오류 반환 |
| `RealRobotControl` | Real 수동·저수준 제어 계약. 일부 이동·관절 명령은 미지원 |
| `UIMaster` | 선택된 RobotMaster의 상태·진행·Scenario 참조를 UI에 제공 |
| `FR5ManualBinder` | MANUAL 화면의 TCP·RPY·그리퍼 상태 표시. 명령은 발행하지 않음 |

새 스크립트를 만들기 전에 이 표와 실제 호출자를 확인한다. 책임이 실제로 바뀌면
코드 변경과 같은 작업에서 이 표도 갱신한다.

### Mock backend

`MockAssemblyScenarioControl`은 먼저 제품·수량·레시피 메타데이터로 MainServer에
Job을 생성한다. 그 뒤 같은 `job_id`와 씬에서 계산한 source·target 좌표만
`/unity/assembly/start`로 보낸다. HTTP와 ROS의 `accepted=true`는 완료가 아니며,
terminal `COMPLETED`를 받아야 `ExecuteAsync()`가 성공한다.

AssemblySequencer는 Job을 claim해 `RUNNING`으로 전이하고 Unit을 만든 뒤 좌표를
내부 `mock_sim`에 전달한다. Unit 실행, 검사, 재고와 최종 Job 상태는 Sequencer가
갱신한다. 시작 시 중단된 RUNNING Unit은 `FAILED`로 기록하지만 Job은 `RUNNING`으로
남긴다. 좌표는 영속하지 않으므로 재개 시 호출자가 같은 `job_id`와 현재 좌표를 다시
보내야 한다.

### Real backend

Real 상태 수신과 저수준 Move/그리퍼 서비스 경로는 일부 구현되어 있다.
`RealAssemblyScenarioControl.ExecuteAsync()`는 현재 `NotSupportedException`으로
실패하므로 Real 자동 조립은 지원하지 않는다. Real 구현도 Job·Unit·YAML 소유권은
Sequencer에 두고 좌표 획득만 현장 컴포넌트에 맡긴다.

## ROS2 Mock 실행

`mock_sim.py`는 고정 레시피와 Unity observation의 `order`·`part_id`를 검증하고
MoveIt으로 Pick·Place를 실행한다. 실행 중 수동 명령과 새 조립 요청은 거부한다.
직접 실행하면 DB 기록이 없고, AssemblySequencer Mock launch를 사용해야 Job·Unit,
재고와 검사 결과가 기록된다. 실제 작업 상태와 `db_sync_state`는 분리된다.

## MainServer

MainServer는 다음 두 책임만 가진다.

- `production`에서 제품·재고·Job·Unit·불량률을 조회한다.
- 조립 HTTP 요청을 UUID `job_id` 기준으로 `production.jobs`에 등록한다.

POST 조립 route는 PostgreSQL만 필요하다. `GET /api/v1/assemblies/current`만
`AssemblyGateway`에서 ROS status service를 호출한다. MainServer는 좌표를 받거나
Job 상태를 전이하거나 Unit을 만들지 않는다. `MAIN_SERVER_MODE`는 배포 경로 선택값이며
Job 키나 생산 데이터가 아니다.

## DB와 레시피

- MainServer는 Job 생성과 생산 조회만 담당한다.
- Job 상태 전이와 Unit·검사·재고 쓰기는 AssemblySequencer만 담당한다.
- 레시피 본문과 조립 순서는 YAML·Git이 소유하고 DB에는 `recipe_version`만 기록한다.
- Mock 좌표와 관절·TCP 스트림은 영속 DB에 저장하지 않는다.
- UUID `job_id`가 HTTP 재시도와 모든 비동기 결과의 단일 상관관계 키다.

DB 기준은 [production 설계](DB.md), 품질 파일 기준은 [불량대책서 필드 매핑](../../MAIN_SERVER/templates/불량대책서_필드매핑.md), 레시피 기준은 [레시피 규격](Recipe.md)이다.

## 현재 제한

- 자동 조립 실행은 Mock만 지원하고 동시에 RUNNING Job과 Unit은 각각 하나다.
- 취소·일시정지 API와 프로세스 재시작 후 좌표 자동 복구는 없다.
- Unity 씬은 한 번의 물리 조립 사이클을 기준으로 구성되어 있다.
- Unity의 제품·작업·품질 화면은 MainServer 조회 API와 완전히 연결되지 않았다.
- Real 자동 조립과 실제 비전 검사는 구현되지 않았다.

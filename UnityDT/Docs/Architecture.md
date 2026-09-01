# 현재 시스템 구조

이 문서는 현재 코드로 실행되는 Unity·MainServer·ROS2·DB 경계를 설명한다. HTTP 계약은 [MainServer API](../../MAIN_SERVER/Main_serverAPI.md), 조립 실행 계약은 [AssemblySequencer API](../../ASSEMBLY_SEQUENCER/API.md)를 따른다.

## 전체 구조

```text
Unity Scenario ── RobotMaster ── MockAssemblyScenarioControl
                                      │ HTTP POST /api/v1/assemblies
                                      ▼
                                  MainServer
                                      │ INSERT
                                      ▼
                         PostgreSQL control.assembly_requests
                                      │ poll + atomic claim
                                      ▼
                         AssemblySequencer Mock Node
                              ├─ 내부 mock_sim ── MoveIt
                              └─ DB Writer ── production DB

Unity ←─ /unity/assembly/feedback ── AssemblySequencer
Unity·MainServer ── status only ──→ /unity/assembly/start
```

자동 조립 명령은 항상 Unity → MainServer → PostgreSQL → AssemblySequencer의
3계층 경로를 사용한다. ROS2 외부 service는 상태 조회에만 사용한다.

## Unity 조립 흐름

`RobotMaster`는 Mock/Real backend를 선택하는 유일한 위치다.

```text
RobotMaster
  ├─ Scenario에 IRobotScenarioControl 주입
  └─ 선택 backend의 상태와 IRobotControl 노출 (수동 UI 명령 미연결)

Scenario
  → MockConveyor.MoveBoardToAssemblyAsync()
  → IRobotScenarioControl.ExecuteAsync()
```

Scenario는 좌표, ROS 메시지, Mock/Real 분기와 완료 callback을 해석하지 않는다. 선택된 backend의 `ExecuteAsync()`가 입력 검증, 통신, 완성 PCB 이송, 실제 완료, 실패와 타임아웃을 책임진다.

## Unity 핵심 스크립트 책임

| 소유자 | 현재 책임 |
|---|---|
| `RobotMaster` | Mock/Real backend 선택·초기화와 Scenario·상태·제어 계약 노출 |
| `Scenario` | 컨베이어 이동과 조립 요청의 상위 순서 |
| `MockAssemblyScenarioControl` | Mock 자동 조립 요청·상태 복구·feedback 완료 판정과 씬 부품 반영 |
| `MockRobotControl` | Mock 수동·저수준 ROS 명령과 명령 완료 판정 |
| `RealAssemblyScenarioControl` | Real 자동 조립 계약 경계. 현재는 미지원 오류 반환 |
| `RealRobotControl` | Real 수동·저수준 제어 계약. 일부 이동·관절 명령은 미지원 |
| `UIMaster` | 선택된 RobotMaster의 상태·진행·Scenario 참조를 UI에 제공 |
| `FR5ManualBinder` | MANUAL 화면의 TCP·RPY·그리퍼 상태 표시. 명령은 발행하지 않음 |

새 스크립트를 만들기 전에 이 표와 실제 호출자를 확인한다. 책임이 실제로 바뀌면 코드 변경과 같은 작업에서 이 표도 갱신한다.

### Mock backend

`MockAssemblyScenarioControl`은 씬의 부품·슬롯과 완성 PCB Transform을 command로
만들어 MainServer HTTP API에 보낸다. HTTP `accepted=true`는 PostgreSQL 저장만
뜻한다. `/unity/assembly/feedback`의 terminal 상태가 `COMPLETED`일 때만
`ExecuteAsync()`가 성공한다.

활성화될 때 ROS service에 `status`를 요청해 최근 스냅샷과 씬 상태를 복구한다.
`QUEUED` command는 PostgreSQL에 남지만 실행 중 Sequencer가 재시작되면 해당
`RUNNING` 요청은 `FAILED`로 마감하며 로봇 동작을 자동 재개하지 않는다.

### Real backend

Real 상태 수신과 저수준 Move/그리퍼 서비스 경로는 일부 구현되어 있다. `RealAssemblyScenarioControl.ExecuteAsync()`는 현재 `NotSupportedException`으로 실패하므로 Real 자동 조립은 지원하지 않는다.

## ROS2 Mock 실행

`mock_sim.py`는 고정 레시피와 Unity observation의 `order`·`part_id`를 검증하고 MoveIt으로 Pick·Place를 실행한다. 실행 중 수동 명령과 새 조립 요청은 거부한다.

직접 `mock_sim.py`를 실행하면 DB 기록이 없다. AssemblySequencer Mock launch는
외부 status service와 feedback 이름을 유지하고 내부 Mock 노드를 remap한다.
PostgreSQL에서 가장 오래된 `QUEUED` 요청을 claim하면서 Job·Unit을 한
transaction으로 만들고, 실제 완료 이후 재고·검사·Job 갱신은 내부 FIFO Worker가
순서대로 반영한다. 실제 작업 상태와 `db_sync_state`는 분리된다.

## MainServer

MainServer는 현재 다음 두 책임을 가진다.

- `production`에서 제품·재고·작업·Unit·불량률을 조회한다.
- 조립 HTTP 요청을 `control.assembly_requests`에 idempotent하게 저장한다.

POST 조립 route는 PostgreSQL만 필요하다. `GET /api/v1/assemblies/current`만
`AssemblyGateway`에서 ROS status service를 호출하므로 이 route를 사용할 때
`rclpy`와 `fairino_msgs`가 필요하다. MainServer는 좌표, 레시피 실행과 로봇 완료를
판정하지 않는다.

## DB와 레시피

- `production` 쓰기는 AssemblySequencer의 `DbWriter`와 `ProductionStore`만 담당한다.
- MainServer는 `production`을 읽고 직접 수정하지 않으며, command queue인
  `control.assembly_requests`만 기록한다.
- 레시피 본문과 좌표는 YAML·Git이 소유하며 DB에는 실행한 `recipe_version`만 기록한다.
- 관절·TCP 스트림과 조립 스텝 callback은 영속 DB에 저장하지 않는다.

DB 기준은 [production 설계](DB.md), 품질 파일 기준은 [불량대책서 필드 매핑](../../MAIN_SERVER/templates/불량대책서_필드매핑.md), 레시피 기준은 [레시피 규격](Recipe.md)이다.

## 현재 제한

- 자동 조립은 Mock, 고정 레시피, 수량 1개와 동시 작업 1건만 지원한다.
- PostgreSQL 단일 FIFO queue만 있으며 취소, 다중 셀 배정과 ROS2 Action 계약은 없다.
- Unity의 제품·작업·품질 화면은 MainServer 조회 API와 완전히 연결되지 않았다.
- Real 자동 조립과 실제 비전 검사는 구현되지 않았다.

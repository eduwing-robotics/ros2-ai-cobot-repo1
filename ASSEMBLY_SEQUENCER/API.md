# Real Assembly API & Implementation Contract

이 문서는 `real_assembly` ROS 2 프로세스를 구현할 실제 로봇 작업자의 계약 기준이다. 전체 API 목록은 [`docs/API.md`](../docs/API.md), 책임·DB 정책은 [`README.md`](README.md)를 따른다.

현재 `real_assembly` 노드와 `real_assembly_interfaces` 패키지는 미구현이다. 아래 Unity·DB 경계는 구현 전에 고정하고, 실제 FR5 동작 순서·속도·좌표와 장비별 timeout은 현장 검증으로 확정한다.

## 1. 시스템 경계

```text
Unity RealAssemblyScenarioControl ─┐
                                   ├─ Start/Status/Progress ─→ real_assembly
MainServer AssemblyGateway(향후) ──┘                               │
                                                                   ├─ FR5
                                                                   ├─ Conveyor
                                                                   ├─ Inspection
                                                                   └─ Async DB Worker ─→ PostgreSQL
```

- `real_assembly`는 MainServer와 독립된 ROS 2 프로세스다.
- MainServer는 조회와 향후 요청 전달만 담당하며 생산 DB를 수정하지 않는다.
- `accepted`는 작업 완료가 아니라 요청 검증과 DB Job·Unit 예약 성공을 뜻한다.
- `COMPLETED`는 실제 조립과 검사가 끝났다는 뜻이다.
- DB 최종 반영 여부는 `db_sync_state`로 별도 관리한다.

## 2. Unity ↔ Assembly Sequencer

### ROS-ASM-003 자동 조립 시작

| 항목 | 내용 |
| --- | --- |
| 호출자 | Unity `RealAssemblyScenarioControl`, 향후 MainServer `AssemblyGateway` |
| 제공자 | `real_assembly` |
| 구분 | ROS 2 Service |
| 인터페이스 | `/real/assembly/start` |
| 타입 | `real_assembly_interfaces/srv/StartAssembly` |
| 상태 | 계약 확정·IDL/실행 노드 미구현 |

계약 IDL은 다음과 같다.

```text
string request_id
string product_code
string product_version
string recipe_version
uint32 requested_quantity
---
bool accepted
string request_id
int64 job_id
int64 unit_id
string error_code
string message
```

구현자는 다음을 지켜야 한다.

- `request_id`는 호출자가 생성한 UUID 문자열로 사용하고 중복 요청에서 새 Job을 만들지 않는다.
- 현재 `requested_quantity`는 `1`만 허용한다.
- 활성 작업이 있으면 `BUSY`로 거절한다.
- 안전·로봇 준비 상태와 요청값을 검증한다.
- DB Worker에서 Job·Unit 생성과 재고 검증이 성공한 뒤에만 `accepted=true`를 반환한다.
- 서비스 callback에서 실제 Pick·Place를 실행하지 않고 작업 Runner를 예약한다.
- `accepted=true` 반환 후 발생한 실행 실패는 Progress의 terminal `FAILED`로 전달한다.

시작 오류 코드는 다음으로 고정한다.

| 오류 코드 | 조건 |
| --- | --- |
| `INVALID_REQUEST` | 필수값·형식·수량 오류 |
| `DUPLICATE_REQUEST` | 같은 `request_id`의 의미가 기존 요청과 다름 |
| `BUSY` | 다른 작업이 실행 중 |
| `DB_UNAVAILABLE` | Job·Unit 예약 또는 재고 검증 불가 |
| `STOCK_UNAVAILABLE` | 필요 재고 부족 |
| `SAFETY_NOT_READY` | 안전 상태가 작업 시작을 허용하지 않음 |
| `ROBOT_UNAVAILABLE` | FR5 명령·상태 경계가 준비되지 않음 |
| `INTERNAL_ERROR` | 분류되지 않은 내부 오류 |

### ROS-ASM-004 상태 조회

| 항목 | 내용 |
| --- | --- |
| 호출자 | Unity `RealAssemblyScenarioControl` |
| 제공자 | `real_assembly` |
| 구분 | ROS 2 Service |
| 인터페이스 | `/real/assembly/status` |
| 타입 | `real_assembly_interfaces/srv/GetAssemblyStatus` |
| 상태 | 계약 확정·IDL/실행 노드 미구현 |

```text
string request_id
---
bool found
string request_id
int64 job_id
int64 unit_id
string state
string current_step
uint32 completed_steps
uint32 total_steps
string db_sync_state
string error_code
string message
builtin_interfaces/Time updated_at
```

- `request_id`가 비어 있으면 현재 활성 작업 또는 최근 terminal snapshot을 반환한다.
- 재접속 복구는 이 Service를 사용한다.
- 현재 snapshot은 ROS 프로세스 메모리 기준이며 프로세스 재시작을 넘는 복구는 보장하지 않는다.

### ROS-ASM-005 진행·완료·실패

| 항목 | 내용 |
| --- | --- |
| 송신자 | `real_assembly` |
| 수신자 | Unity `RealAssemblyScenarioControl` |
| 구분 | ROS 2 Topic |
| 인터페이스 | `/real/assembly/progress` |
| 타입 | `real_assembly_interfaces/msg/AssemblyProgress` |
| QoS | Reliable, Volatile, depth 10 |
| 상태 | 계약 확정·IDL/실행 노드 미구현 |

```text
builtin_interfaces/Time stamp
string request_id
int64 job_id
int64 unit_id
string state
string current_step
uint32 completed_steps
uint32 total_steps
string db_sync_state
string error_code
string message
```

허용 상태는 다음과 같다.

```text
STARTED → PICKED → PLACED → INSPECTING → COMPLETED
                                      └→ FAILED
```

- `COMPLETED`와 `FAILED`는 terminal이며 요청당 한 번만 발행한다.
- 서비스 응답이나 명령 수락만으로 다음 상태로 전환하지 않는다.
- `request_id`가 현재 활성 요청과 다르면 해당 callback을 폐기한다.
- terminal 상태는 실제 하위 동작 결과, timeout 또는 안전 상태를 근거로 결정한다.
- terminal 발행 뒤 변경되는 DB 동기화 상태는 Status Service에서 확인한다.

실행 오류 코드는 다음을 기본으로 한다.

| 오류 코드 | 조건 |
| --- | --- |
| `ROBOT_TIMEOUT` | FR5 실제 완료 대기 timeout |
| `ROBOT_FAULT` | FR5 fault 또는 명령 실패 |
| `CONVEYOR_FAILED` | 컨베이어 이동 실패 |
| `INSPECTION_FAILED` | 검사 Action 실패·결과 오류 |
| `SAFETY_STOP` | 사람 감지·E-STOP 등 안전 중단 |
| `DB_SYNC_FAILED` | 작업 상태는 유지하고 `db_sync_state=FAILED`로 기록 |
| `EXECUTION_FAILED` | 분류되지 않은 실행 실패 |

`db_sync_state` 값은 `NOT_STARTED`, `PENDING`, `SYNCED`, `FAILED`로 제한한다.

## 3. Real 장비 경계

### FR5

| API ID | 기능 | 인터페이스 | 구현자 요구사항 |
| --- | --- | --- | --- |
| ROS-RBT-007 | 이동·그리퍼 명령 | `/fairino_remote_command_service` | 입력·단위 검증, 명령 실패 전달, 명령 수락과 완료 구분 |
| ROS-RBT-008 | 로봇 상태 | `/nonrt_state_data` | 관절·TCP·그리퍼·fault·안전 상태로 실제 완료 판정 |

- Service 응답만으로 이동·그리퍼 완료를 판정하지 않는다.
- 좌표계와 단위는 각 명령 경계에서 한 번만 변환한다.
- 로봇 상태 callback에는 DB·MainServer 호출을 넣지 않는다.
- 작업 중 수동 명령과 신규 자동 조립 요청은 거절한다.

### Conveyor·Inspection·Safety

다음 계약은 상대 컴포넌트 담당자와 합의 전까지 이름과 메시지 타입을 확정하지 않는다.

| API ID | 호출자·송신자 → 제공자·수신자 | 구분 | 필수 계약 | 상태 |
| --- | --- | --- | --- | --- |
| ROS-CNV-001 | `real_assembly` → `conveyor_controller` | Action | 목표 위치, 완료 위치, timeout, 오류 코드 | 제안·협의 필요 |
| ROS-STA-002 | `conveyor_controller` → `real_assembly`, Unity | Topic | 현재 위치, 운전·정지·오류 상태 | 제안·협의 필요 |
| ROS-INS-001 | `real_assembly` → `inspection_node` | Action | Goal·Feedback·Result 아래 정의 | 제안·협의 필요 |
| ROS-SAF-001 | Safety bridge → `real_assembly`, 명령 경계, Unity | Topic | 안전 허용, 정지 원인, 복구 여부 | 제안·협의 필요 |

Inspection 최소 계약은 다음과 같다.

```text
Goal: job_id, unit_id, product_id
Feedback: stage, progress, message
Result: result(PASS/FAIL), slot_code, defect_type,
        image_path, inspected_at, error_code, message
```

물리 E-STOP은 하드와이어드 안전회로가 수행한다. ROS 2는 상태 전달, 신규 명령 차단과 작업 실패 전환을 담당한다.

## 4. 생산 DB 계약

| 구분 | 소유자 | 연결·권한 |
| --- | --- | --- |
| 조회 | MainServer | `MAIN_SERVER_DB_DSN`, read-only |
| 쓰기 | `real_assembly`의 Async DB Worker | `PRODUCTION_DB_DSN`, `production_writer` |

### 작업 시작 전 필수 transaction

실제 로봇 동작 전에 다음 순서가 성공해야 한다.

1. `start_job(product_code, product_version, quantity, recipe_version)`
2. `start_next_unit(job_id)`
3. 반환된 `job_id`, `unit_id`를 활성 작업 상태에 저장
4. `accepted=true` 반환 후 Runner 시작

DB를 사용할 수 없거나 재고가 부족하면 실제 로봇을 움직이지 않는다.

### 실행 후 비동기 갱신

| 이벤트 | ProductionStore 처리 |
| --- | --- |
| `ASSEMBLY_COMPLETED` | `complete_assembly_and_consume_stock(unit_id)` |
| `INSPECTION_RECORDED` | `record_inspection(unit_id, result, defects, image_path)` |
| `JOB_FINISHED` | `finish_job(job_id, final_status)` |

```text
Robot·Inspection callback
  → DbUpdateEvent enqueue
  → callback 반환

Async DB Worker
  → FIFO transaction
  → commit 성공 후 queue 제거
  → 실패 시 backoff 재시도
```

`DbUpdateEvent` 최소 필드는 다음과 같다.

```text
event_id
event_type
job_id
unit_id
payload
created_at
attempt_count
next_retry_at
last_error
```

- Raw SQL 문자열을 queue에 저장하지 않는다.
- queue는 bounded로 구성하고 overflow를 조용히 폐기하지 않는다.
- PostgreSQL commit 성공 전에는 항목을 제거하지 않는다.
- 한 작업의 이벤트 순서를 보장하는 단일 Worker를 우선 사용한다.
- 재시도로 중복 적용될 수 있으므로 Store 처리는 `event_id` 또는 DB 상태 기준으로 멱등해야 한다.
- 관절·TCP 스트림과 고빈도 상태는 생산 DB에 저장하지 않는다.
- 현재 queue는 프로세스 재시작을 넘는 영속성을 보장하지 않는다.

## 5. 구현자가 지켜야 할 사항

### 해야 할 일

- 공개 endpoint·필드·terminal 의미를 변경하지 않고 구현한다.
- 모든 비동기 결과를 `request_id`로 현재 작업과 대조한다.
- 실제 완료, timeout, 취소와 실패를 호출자에게 전달한다.
- 안전 중단은 업무 상태와 무관하게 최우선 처리한다.
- 실패 후 활성 작업, pending goal과 임시 상태를 정리한다.
- 실제 로봇에서 확인한 좌표계·단위·완료 조건·timeout을 문서에 반영한다.
- `RealAssemblyScenarioControl.ExecuteAsync()`가 terminal 결과 전에는 성공하지 않게 한다.

### 하지 말아야 할 일

- MainServer를 로봇 실행이나 DB 쓰기의 필수 경로로 두지 않는다.
- ROS callback에서 PostgreSQL 응답을 기다리거나 SQL을 직접 실행하지 않는다.
- Service 명령 수락을 실제 동작 완료로 취급하지 않는다.
- Sequencer에 좌표 변환, vendor 명령 문자열 생성과 상태 해석을 중복 구현하지 않는다.
- Mock 전용 클래스·토픽·Scene Transform을 Real 구현에서 참조하지 않는다.
- 협의되지 않은 Conveyor·Inspection·Safety endpoint를 임의로 확정하지 않는다.
- 미구현 기능을 API 문서에서 구현으로 표시하지 않는다.

## 6. 구현 완료 조건

- 같은 `request_id` 재호출이 새 Job을 만들지 않는다.
- 동시 작업 요청이 `BUSY`로 거절된다.
- MainServer 종료 후에도 이미 수락된 작업이 계속된다.
- DB 예약 실패 시 실제 로봇이 움직이지 않는다.
- DB 지연 중에도 로봇·안전 callback이 처리된다.
- DB 복구 후 pending 이벤트가 순서대로 반영되고 commit 후 제거된다.
- FR5·Conveyor·Inspection timeout이 terminal `FAILED`로 전달된다.
- E-STOP 발생 시 신규 명령이 차단되고 활성 작업이 실패 처리된다.
- `COMPLETED`는 실제 조립·검사가 완료된 경우에만 발행된다.

## 7. 현재 범위 밖

- 프로세스 재시작을 넘는 SQLite Outbox
- SECS/GEM·GEM300 Adapter
- 다중 작업 병렬 실행
- 별도 DB Writer 서버·메시지 브로커
- 계약이 확정되지 않은 취소·일시정지·재개

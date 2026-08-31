# Assembly Sequencer API Catalog & Interface Specification

이 문서는 `real_assembly` ROS 2 프로세스 구현 계약이다. 전체 목록은 [`docs/API.md`](../docs/API.md), 프로세스·DB 정책은 [`README.md`](README.md)를 따른다.

| 항목 | 내용 |
| --- | --- |
| 대상 | 실제 로봇 구현자, Unity·MainServer 연동 담당자 |
| 구현 상태 | `real_assembly` 노드와 `real_assembly_interfaces` 패키지 미구현 |
| 확정 범위 | Unity 연동 API, 상태·오류 의미, DB 갱신 정책 |
| 현장 확정 | FR5 동작 순서·속도·좌표, 장비별 timeout, Conveyor·Inspection·Safety 상세 계약 |

## 1. 전체 API 목록

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 |
| --- | --- | --- | --- | --- | --- | --- |
| ROS-ASM-003 | Real 자동 조립 시작 | Unity `RealAssemblyScenarioControl`, 향후 MainServer `AssemblyGateway` → `real_assembly` | Service | `/real/assembly/start` | `real_assembly_interfaces/srv/StartAssembly` | 계약 확정·미구현 |
| ROS-ASM-004 | Real 조립 상태 조회 | Unity `RealAssemblyScenarioControl` → `real_assembly` | Service | `/real/assembly/status` | `real_assembly_interfaces/srv/GetAssemblyStatus` | 계약 확정·미구현 |
| ROS-ASM-005 | 진행·완료·실패 전달 | `real_assembly` → Unity `RealAssemblyScenarioControl` | Topic | `/real/assembly/progress` | `real_assembly_interfaces/msg/AssemblyProgress` | 계약 확정·미구현 |
| ROS-RBT-007 | FR5 이동·그리퍼 명령 | `real_assembly` Robot 경계 → `fr_command_server` | Service | `/fairino_remote_command_service` | `fairino_msgs/srv/RemoteCmdInterface` | 저수준 부분 구현 |
| ROS-RBT-008 | FR5 상태 전달 | `fr_command_server` → `real_assembly` | Topic | `/nonrt_state_data` | `fairino_msgs/msg/RobotNonrtState` | 구현 |
| ROS-CNV-001 | 컨베이어 위치 이동 | `real_assembly` → `conveyor_controller` | Action | `TBD` | `TBD` | 제안·협의 필요 |
| ROS-STA-002 | 컨베이어 상태 전달 | `conveyor_controller` → `real_assembly`, Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 |
| ROS-INS-001 | 검사 실행·결과 반환 | `real_assembly` → `inspection_node` | Action | `TBD` | `TBD` | 제안·협의 필요 |
| ROS-SAF-001 | 안전 상태 전달 | Safety bridge → `real_assembly`, 명령 경계, Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 |

## 2. 공통 계약

| 항목 | 계약 |
| --- | --- |
| 프로세스 경계 | `real_assembly`는 MainServer와 독립 실행한다. |
| MainServer 중단 | 이미 수락된 작업과 DB 갱신은 계속한다. MainServer 경유 신규 요청만 불가하다. |
| 요청 수락 | `accepted=true`는 입력 검증과 DB Job·Unit 예약 성공이다. 작업 완료가 아니다. |
| 작업 완료 | `COMPLETED`는 실제 조립과 검사가 모두 완료된 상태다. |
| DB 상태 | 실제 작업 상태와 `db_sync_state`를 분리한다. |
| 동시 실행 | 활성 작업은 1개만 허용하며 추가 요청은 `BUSY`로 거절한다. |
| 요청 식별 | 호출자가 UUID 문자열 `request_id`를 생성하고 모든 비동기 결과를 대조한다. |
| 중복 요청 | 같은 ID·같은 요청은 기존 결과를 반환하고, 같은 ID·다른 요청은 `DUPLICATE_REQUEST`로 거절한다. |
| 완료 판정 | 명령 수락 응답이 아니라 실제 장비 상태, 검사 결과, timeout을 기준으로 판정한다. |
| 재접속 | `/real/assembly/status`로 활성 작업 또는 최근 terminal snapshot을 조회한다. |
| 재시작 복구 | 현재 snapshot과 DB queue는 프로세스 재시작 이후 복구를 보장하지 않는다. |

## 3. ROS-ASM-003 자동 조립 시작

### 3.1 기본 명세

| 항목 | 내용 |
| --- | --- |
| 목적 | 제품 1개의 Real 조립 작업을 검증·예약하고 실행 Runner를 시작한다. |
| 호출자 | Unity `RealAssemblyScenarioControl`, 향후 MainServer `AssemblyGateway` |
| 제공자 | `real_assembly` |
| 구분 | ROS 2 Service |
| 인터페이스 | `/real/assembly/start` |
| 타입 | `real_assembly_interfaces/srv/StartAssembly` |
| 성공 조건 | DB Job·Unit 예약 후 `accepted=true` |
| 멱등성 | `request_id` 기준 보장 |
| 상태 | 계약 확정·IDL/실행 노드 미구현 |

### 3.2 요청 필드

| 필드 | 타입 | 필수 | 제약조건 | 설명 |
| --- | --- | :---: | --- | --- |
| `request_id` | string | Y | UUID 문자열 | 요청·결과 상관관계 및 중복 방지 ID |
| `product_code` | string | Y | 비어 있지 않음 | 생산 제품 코드 |
| `product_version` | string | Y | 비어 있지 않음 | 제품 버전 |
| `recipe_version` | string | Y | 비어 있지 않음 | 조립 레시피 버전 |
| `requested_quantity` | uint32 | Y | 현재는 `1`만 허용 | 요청 수량 |

### 3.3 응답 필드

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `accepted` | bool | 검증과 DB 예약 성공 여부 |
| `request_id` | string | 요청 ID |
| `job_id` | int64 | 생성되거나 기존에 매핑된 Job ID |
| `unit_id` | int64 | 생성되거나 기존에 매핑된 Unit ID |
| `error_code` | string | 실패 코드, 성공 시 빈 문자열 |
| `message` | string | 처리 결과 설명 |

### 3.4 처리 순서

| 순서 | 처리 | 실패 시 |
| :---: | --- | --- |
| 1 | 필수값·형식·수량과 중복 요청 확인 | 요청 거절 |
| 2 | 안전·FR5 준비 상태와 활성 작업 확인 | 요청 거절 |
| 3 | `start_job(product_code, product_version, quantity, recipe_version)` | 로봇 미동작·요청 거절 |
| 4 | `start_next_unit(job_id)` 및 재고 검증 | 로봇 미동작·요청 거절 |
| 5 | `job_id`, `unit_id`를 활성 상태에 저장 | 요청 거절 |
| 6 | `accepted=true` 반환 후 Runner 예약 | 이후 실패는 Progress `FAILED` |

Service callback에서는 실제 Pick·Place를 실행하지 않는다.

### 3.5 오류 명세

| 오류 코드 | 발생 조건 |
| --- | --- |
| `INVALID_REQUEST` | 필수값·형식·수량 오류 |
| `DUPLICATE_REQUEST` | 같은 `request_id`에 다른 요청 내용 사용 |
| `BUSY` | 다른 작업 실행 중 |
| `DB_UNAVAILABLE` | Job·Unit 예약 또는 재고 검증 불가 |
| `STOCK_UNAVAILABLE` | 필요 재고 부족 |
| `SAFETY_NOT_READY` | 안전 상태가 시작을 허용하지 않음 |
| `ROBOT_UNAVAILABLE` | FR5 명령·상태 경계가 준비되지 않음 |
| `INTERNAL_ERROR` | 분류되지 않은 내부 오류 |

## 4. ROS-ASM-004 상태 조회

### 4.1 기본 명세

| 항목 | 내용 |
| --- | --- |
| 목적 | 활성 작업 또는 최근 terminal snapshot을 조회한다. |
| 호출자 | Unity `RealAssemblyScenarioControl` |
| 제공자 | `real_assembly` |
| 구분 | ROS 2 Service |
| 인터페이스 | `/real/assembly/status` |
| 타입 | `real_assembly_interfaces/srv/GetAssemblyStatus` |
| 상태 | 계약 확정·IDL/실행 노드 미구현 |

### 4.2 요청 필드

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `request_id` | string | N | 비어 있으면 활성 작업 또는 최근 terminal snapshot 조회 |

### 4.3 응답 필드

| 필드 | 타입·형식 | Nullable | 설명 |
| --- | --- | :---: | --- |
| `found` | bool | N | 조회 결과 존재 여부 |
| `request_id` | string | N | 요청 ID |
| `job_id` | int64 | N | Job ID |
| `unit_id` | int64 | N | Unit ID |
| `state` | string(enum) | N | 현재 작업 상태 |
| `current_step` | string | N | 현재 실행 단계 |
| `completed_steps` | uint32 | N | 완료 단계 수 |
| `total_steps` | uint32 | N | 전체 단계 수 |
| `db_sync_state` | string(enum) | N | DB 동기화 상태 |
| `error_code` | string | N | 작업 또는 동기화 오류 코드 |
| `message` | string | N | 상태 설명 |
| `updated_at` | `builtin_interfaces/Time` | N | 마지막 갱신 시각 |

## 5. ROS-ASM-005 진행·완료·실패

### 5.1 기본 명세

| 항목 | 내용 |
| --- | --- |
| 목적 | 실제 조립 진행, terminal 결과와 당시 DB 동기화 상태를 전달한다. |
| 송신자 | `real_assembly` |
| 수신자 | Unity `RealAssemblyScenarioControl` |
| 구분 | ROS 2 Topic |
| 인터페이스 | `/real/assembly/progress` |
| 타입 | `real_assembly_interfaces/msg/AssemblyProgress` |
| QoS | Reliable, Volatile, depth 10 |
| 상태 | 계약 확정·IDL/실행 노드 미구현 |

### 5.2 메시지 필드

| 필드 | 타입·형식 | 설명 |
| --- | --- | --- |
| `stamp` | `builtin_interfaces/Time` | 발행 시각 |
| `request_id` | string | 요청 ID |
| `job_id` | int64 | Job ID |
| `unit_id` | int64 | Unit ID |
| `state` | string(enum) | 작업 상태 |
| `current_step` | string | 현재 실행 단계 |
| `completed_steps` | uint32 | 완료 단계 수 |
| `total_steps` | uint32 | 전체 단계 수 |
| `db_sync_state` | string(enum) | 발행 시점 DB 동기화 상태 |
| `error_code` | string | 실패 코드 |
| `message` | string | 진행·실패 설명 |

### 5.3 작업 상태

| 상태 | 의미 | Terminal |
| --- | --- | :---: |
| `IDLE` | 활성 작업 없음, Status에서만 사용 | N |
| `STARTED` | 작업 수락 후 실행 시작 | N |
| `PICKED` | 부품 Pick 실제 완료 | N |
| `PLACED` | 부품 Place 실제 완료 | N |
| `INSPECTING` | 검사 실행 중 | N |
| `COMPLETED` | 조립·검사 실제 완료 | Y |
| `FAILED` | 하위 동작·검사·안전·timeout 실패 | Y |

`COMPLETED`와 `FAILED`는 요청당 한 번만 발행한다. terminal 발행 뒤 바뀐 DB 상태는 Status Service로 확인한다.

### 5.4 DB 동기화 상태

| 상태 | 의미 |
| --- | --- |
| `NOT_STARTED` | 후속 DB 이벤트 미생성 |
| `PENDING` | queue 대기 또는 재시도 중 |
| `SYNCED` | PostgreSQL commit 완료 |
| `FAILED` | 최종 동기화 실패, 작업 terminal 상태는 변경하지 않음 |

### 5.5 실행 오류 명세

| 오류 코드 | 발생 조건 |
| --- | --- |
| `ROBOT_TIMEOUT` | FR5 실제 완료 대기 timeout |
| `ROBOT_FAULT` | FR5 fault 또는 명령 실패 |
| `CONVEYOR_FAILED` | 컨베이어 이동 실패 |
| `INSPECTION_FAILED` | 검사 Action 실패 또는 결과 오류 |
| `SAFETY_STOP` | 사람 감지·E-STOP 등 안전 중단 |
| `EXECUTION_FAILED` | 분류되지 않은 실행 실패 |
| `DB_SYNC_FAILED` | DB 갱신 최종 실패, `db_sync_state=FAILED` |

## 6. 하위 컴포넌트 계약

### 6.1 FR5

| API ID | 입력·출력 | 구현 요구사항 |
| --- | --- | --- |
| ROS-RBT-007 | 이동·그리퍼 명령 | 입력·좌표계·단위 검증, 명령 실패 전달, 수락과 완료 구분 |
| ROS-RBT-008 | 관절·TCP·그리퍼·fault·안전 상태 | 실제 완료·실패·timeout 판정 |

| 공통 규칙 | 내용 |
| --- | --- |
| 완료 판정 | Service 응답만으로 이동·그리퍼 완료를 판정하지 않는다. |
| 변환 | 좌표계와 단위는 각 하위 공개 경계에서 한 번만 변환한다. |
| callback | 로봇 상태 callback에서 DB·MainServer를 호출하지 않는다. |
| 명령 충돌 | 자동 작업 중 수동 명령과 신규 자동 요청을 거절한다. |
| 현장 값 | 좌표계·단위·속도·허용 오차·timeout은 실기 검증 후 기록한다. |

### 6.2 Conveyor·Inspection·Safety

합의 전에는 endpoint와 메시지 타입을 임의로 확정하지 않는다.

| API ID | 합의할 최소 항목 |
| --- | --- |
| ROS-CNV-001 | 목표 위치, 실제 완료 위치, timeout, 오류 코드 |
| ROS-STA-002 | 현재 위치, 운전·정지·오류 상태, 갱신 주기, QoS |
| ROS-INS-001 | Goal·Feedback·Result, timeout, 취소·실패 조건 |
| ROS-SAF-001 | 작업 허용 여부, 정지 원인, 복구 가능 여부, QoS |

| Inspection 구분 | 필드 |
| --- | --- |
| Goal | `job_id`, `unit_id`, `product_id` |
| Feedback | `stage`, `progress`, `message` |
| Result | `result(PASS/FAIL)`, `slot_code`, `defect_type`, `image_path`, `inspected_at`, `error_code`, `message` |

물리 E-STOP은 하드와이어드 안전회로가 수행한다. ROS 2는 상태 전달, 신규 명령 차단과 작업 실패 전환을 담당한다.

## 7. 내부 DB 계약

### 7.1 소유권·권한

| 구분 | 소유자 | 연결 | 권한 |
| --- | --- | --- | --- |
| 조회 | MainServer | `MAIN_SERVER_DB_DSN` | read-only |
| 쓰기 | `real_assembly` Async DB Worker | `PRODUCTION_DB_DSN` | `production_writer` |

### 7.2 내부 인터페이스

| ID | 기능명 | 송신자 → 수신자 | 구분 | 상태 |
| --- | --- | --- | --- | --- |
| INT-DB-001 | 생산 DB 갱신 예약 | Sequencer 업무 흐름 → Async DB Worker | bounded in-process queue | 설계됨·미구현 |
| INT-DB-002 | 생산 DB transaction 적용 | Async DB Worker → PostgreSQL | DB transaction | 설계됨·미구현 |

### 7.3 이벤트 처리

| 이벤트 | ProductionStore 처리 |
| --- | --- |
| `ASSEMBLY_COMPLETED` | `complete_assembly_and_consume_stock(unit_id)` |
| `INSPECTION_RECORDED` | `record_inspection(unit_id, result, defects, image_path)` |
| `JOB_FINISHED` | `finish_job(job_id, final_status)` |

| `DbUpdateEvent` 필드 | 설명 |
| --- | --- |
| `event_id` | 중복 적용 방지 식별자 |
| `event_type` | DB 갱신 종류 |
| `job_id`, `unit_id` | 작업 식별자 |
| `payload` | Store 호출에 필요한 데이터, Raw SQL 금지 |
| `created_at` | 이벤트 생성 시각 |
| `attempt_count` | 시도 횟수 |
| `next_retry_at` | 다음 재시도 시각 |
| `last_error` | 최근 오류 |

### 7.4 Queue 정책

| 항목 | 정책 |
| --- | --- |
| callback | 상태 확정 후 이벤트를 enqueue하고 즉시 반환한다. SQL을 실행하거나 DB 응답을 기다리지 않는다. |
| 순서 | 한 작업의 순서를 보장하는 bounded FIFO·단일 Worker를 우선 사용한다. |
| 제거 | PostgreSQL commit 성공 후에만 제거한다. 검사 callback이 제거하지 않는다. |
| 실패 | backoff 재시도하며 overflow와 최종 실패를 조용히 폐기하지 않는다. |
| 멱등성 | 재시도 중복에 대비해 `event_id` 또는 DB 상태로 보장한다. |
| 저장 제외 | 관절·TCP 스트림과 고빈도 상태는 생산 DB에 저장하지 않는다. |
| 영속성 | 현재 queue는 프로세스 재시작을 넘는 보존을 보장하지 않는다. |

## 8. 실 로봇 구현자 준수사항

| 구분 | 지켜야 할 내용 |
| --- | --- |
| 공개 계약 | endpoint·필드·상태·terminal 의미를 변경하지 않는다. 변경은 Unity 담당자와 먼저 합의한다. |
| 상관관계 | 모든 비동기 결과를 `request_id`로 활성 작업과 대조한다. 다른 요청의 callback은 폐기한다. |
| 실행 완료 | `ExecuteAsync()`는 terminal 결과 전에는 성공으로 끝내지 않는다. |
| 하위 경계 | 검증·변환·통신·실제 완료 감지·timeout·실패 전달을 각 하위 공개 진입점에서 완결한다. |
| Sequencer | 작업 순서와 중단·건너뛰기·재시도 정책만 둔다. 좌표 변환·vendor 명령·SQL을 넣지 않는다. |
| 안전 | 안전 중단을 최우선 처리하고 신규 명령을 차단한다. |
| 정리 | 실패 후 활성 작업, pending goal과 임시 상태를 정리한다. |
| DB | callback은 이벤트만 enqueue하며 MainServer에 생산 DB 쓰기를 위임하지 않는다. |
| Mock 분리 | Mock 클래스·토픽·Scene Transform을 Real 구현에서 참조하지 않는다. |
| 문서화 | 실기 확인한 좌표계·단위·완료 조건·timeout을 본 문서에 반영한다. |

## 9. 구현 완료 확인

| 확인 항목 | 기대 결과 |
| --- | --- |
| 같은 `request_id` 재호출 | 새 Job 미생성 |
| 동시 요청 | `BUSY` 반환 |
| MainServer 종료 | 이미 수락된 작업 계속 실행 |
| DB 예약·재고 검증 실패 | 실제 로봇 미동작 |
| DB 지연 | 로봇·안전 callback 정상 처리 |
| DB 복구 | pending 이벤트 순서 적용, commit 후 제거 |
| FR5·Conveyor·Inspection timeout | terminal `FAILED` 전달 |
| E-STOP | 신규 명령 차단, 활성 작업 실패 전환 |
| 정상 작업 | 실제 조립·검사 완료 후에만 `COMPLETED` 발행 |

## 10. 미확정·현재 범위 밖

| 항목 | 상태 |
| --- | --- |
| Conveyor·Inspection·Safety endpoint·Schema·QoS·timeout | 담당자 합의 필요 |
| 조립 취소·일시정지·재개 API | 계약 합의 전 미구현 |
| 프로세스 재시작을 넘는 SQLite Outbox | 현재 범위 밖 |
| SECS/GEM·GEM300 Adapter | 현재 범위 밖 |
| 다중 작업 병렬 실행 | 현재 범위 밖 |
| 별도 DB Writer 서버·메시지 브로커 | 현재 범위 밖 |

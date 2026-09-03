# Assembly Sequencer API Catalog & Interface Specification

이 문서는 `real_assembly` ROS 2 프로세스 구현 계약이다. 프로세스·DB 정책은 [`README.md`](README.md)를 따른다.

| 항목 | 내용 |
| --- | --- |
| 대상 | 실제 로봇 구현자, Unity·MainServer 연동 담당자 |
| 구현 상태 | 공통 DB Writer·Mock 노드·공통 Recipe parser 구현, `real_assembly` 실행 노드와 전용 ROS 인터페이스 미구현 |
| 확정 범위 | Recipe schema, Unity 연동 API, 하위 Action 계약, 상태·오류 의미, DB 갱신 정책 |
| 현장 확정 | FR5 taught point·속도·허용 오차, 장비별 timeout·보정값, Safety 상세 계약 |

## 1. 전체 API 목록

| API ID | 기능명 | 호출자·송신자 → 제공자·수신자 | 구분 | 인터페이스 | 메시지 타입 | 상태 |
| --- | --- | --- | --- | --- | --- | --- |
| ROS-ASM-003 | Real backend 자동 조립 시작 | AssemblySequencer Real adapter → `real_assembly` backend | Service | `/real/assembly/start` | `real_assembly_interfaces/srv/StartAssembly` | 내부 연동 계약·미구현 |
| ROS-ASM-004 | Real 조립 상태 조회 | Unity·MainServer → AssemblySequencer Real adapter | Service | `/real/assembly/status` | `real_assembly_interfaces/srv/GetAssemblyStatus` | 계약 확정·미구현 |
| ROS-ASM-005 | 진행·완료·실패 전달 | `real_assembly` backend → AssemblySequencer Real adapter → Unity | Topic | `/real/assembly/progress` | `real_assembly_interfaces/msg/AssemblyProgress` | 계약 확정·미구현 |
| ROS-RBT-007 | FR5 이동·그리퍼 명령 | `real_assembly` Robot 경계 → `fr_command_server` | Service | `/fairino_remote_command_service` | `fairino_msgs/srv/RemoteCmdInterface` | 저수준 부분 구현 |
| ROS-RBT-008 | FR5 상태 전달 | `fr_command_server` → `real_assembly` | Topic | `/nonrt_state_data` | `fairino_msgs/msg/RobotNonrtState` | 구현 |
| ROS-RBT-009 | Real Ghost 목표 자세 미리보기 | `real_assembly` backend → Unity Real Ghost | Topic | `/real/ghost/target` | `geometry_msgs/msg/PoseStamped` | Unity 수신 구현 |
| ROS-VIS-001 | Pick·Place 목표 자세 해석 | `real_assembly` → Pick/Place Vision | Action | `/vision/pick_place/resolve` | `vision_interfaces/action/ResolveAssemblyTargets` | 계약 확정·비전 브랜치 구현 필요 |
| ROS-CNV-001 | 컨베이어 위치 이동 | `real_assembly` → `conveyor_controller` | Action | `/conveyor/move_to_station` | `vision_interfaces/action/MoveConveyorToStation` | 계약 확정·비전/컨베이어 브랜치 구현 필요 |
| ROS-STA-002 | 컨베이어 상태 전달 | `conveyor_controller` → `real_assembly`, Unity | Topic | `/conveyor/state` | `vision_interfaces/msg/ConveyorState` | 계약 확정·비전/컨베이어 브랜치 구현 필요 |
| ROS-INS-001 | 검사 실행·결과 반환 | `real_assembly` → `inspection_node` | Action | `/vision/inspection/run` | `vision_interfaces/action/InspectAssembly` | 계약 확정·검사 비전 브랜치 구현 필요 |
| ROS-SAF-001 | 안전 상태 전달 | Safety bridge → `real_assembly`, 명령 경계, Unity | Topic | `TBD` | `TBD` | 제안·협의 필요 |

## 2. 공통 계약

| 항목 | 계약 |
| --- | --- |
| 프로세스 경계 | `real_assembly`는 MainServer와 독립 실행한다. |
| MainServer 중단 | DB에 적재된 `PENDING` Job과 이미 실행 중인 작업은 유지된다. MainServer 경유 신규 요청만 불가하다. |
| 요청 수락 | HTTP `202`는 PostgreSQL Job 생성 성공이다. backend `accepted=true`도 작업 완료가 아니다. |
| 작업 완료 | `COMPLETED`는 실제 조립과 검사가 모두 완료된 상태다. |
| DB 상태 | 실제 작업 상태와 `db_sync_state`를 분리한다. |
| 동시 실행 | 활성 작업은 1개만 허용하며 추가 Job은 `PENDING`으로 대기한다. |
| 요청 식별 | 호출자가 UUID 문자열 `job_id`를 생성하고 모든 비동기 결과를 대조한다. |
| 중복 요청 | 같은 Job ID·같은 내용은 기존 결과를 반환하고, 같은 Job ID·다른 내용은 `DUPLICATE_REQUEST`로 거절한다. |
| 완료 판정 | 명령 수락 응답이 아니라 실제 장비 상태, 검사 결과, timeout을 기준으로 판정한다. |
| 재접속 | `/real/assembly/status`로 활성 작업 또는 최근 terminal snapshot을 조회한다. |
| 재시작 복구 | PostgreSQL의 `PENDING` Job은 유지한다. 재시작 시 중단된 RUNNING Unit만 FAILED로 마감하고 Job은 RUNNING으로 남긴다. 좌표는 저장하지 않으므로 호출자가 같은 job_id와 새 좌표로 재개한다. |

## 3. ROS-ASM-003 Real backend 자동 조립 시작

외부 자동 조립의 기준 진입점은 MainServer `POST /api/v1/assemblies`다. 아래 ROS Service는 AssemblySequencer가 DB에서 Real 요청을 claim한 뒤 팀원의 Real backend와 연결할 내부 계약이며, IDL과 adapter 구현 전에는 공개 호출 경로가 아니다.

### 3.1 기본 명세

| 항목 | 내용 |
| --- | --- |
| 목적 | AssemblySequencer가 claim한 Real 조립 작업의 실행 Runner를 시작한다. |
| 호출자 | AssemblySequencer Real adapter |
| 제공자 | `real_assembly` backend |
| 구분 | ROS 2 Service |
| 인터페이스 | `/real/assembly/start` |
| 타입 | `real_assembly_interfaces/srv/StartAssembly` |
| 성공 조건 | backend가 실행 요청을 검증·수락한 뒤 `accepted=true` |
| 멱등성 | `job_id` 기준 보장 |
| 상태 | 계약 확정·IDL/실행 노드 미구현 |

### 3.2 요청 필드

| 필드 | 타입 | 필수 | 제약조건 | 설명 |
| --- | --- | :---: | --- | --- |
| `job_id` | string | Y | UUID 문자열 | Job·결과 상관관계 및 HTTP 재시도 중복 방지 ID |
| `product_code` | string | Y | 비어 있지 않음 | 생산 제품 코드 |
| `product_version` | string | Y | 비어 있지 않음 | 제품 버전 |
| `recipe_version` | string | Y | 비어 있지 않음 | 조립 레시피 버전 |
| `requested_quantity` | uint32 | Y | 양의 정수 | 요청 수량 |

### 3.3 응답 필드

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `accepted` | bool | backend 검증과 실행 요청 수락 여부 |
| `job_id` | string(UUID) | Job ID |
| `unit_id` | int64 | 생성되거나 기존에 매핑된 Unit ID |
| `error_code` | string | 실패 코드, 성공 시 빈 문자열 |
| `message` | string | 처리 결과 설명 |

### 3.4 처리 순서

| 순서 | 처리 | 실패 시 |
| :---: | --- | --- |
| 1 | AssemblySequencer가 PostgreSQL Job을 claim하고 Unit 생성·재고 검증을 한 transaction에서 수행 | backend 미호출·요청 실패 |
| 2 | adapter가 필수값·식별자와 중복 요청을 확인 | 요청 거절 |
| 3 | backend가 안전·FR5 준비 상태와 활성 작업을 확인 | 요청 거절 |
| 4 | `job_id`, `unit_id`를 활성 상태에 저장 | 요청 거절 |
| 5 | `accepted=true` 반환 후 Runner 예약 | 이후 실패는 Progress `FAILED` |

Service callback에서는 실제 Pick·Place를 실행하지 않는다.

### 3.5 오류 명세

| 오류 코드 | 발생 조건 |
| --- | --- |
| `INVALID_REQUEST` | 필수값·형식·수량 오류 |
| `DUPLICATE_REQUEST` | 같은 `job_id`에 다른 Job 내용 사용 |
| `BUSY` | 다른 작업 실행 중 |
| `DB_UNAVAILABLE` | Job claim·Unit 생성 또는 재고 검증 불가 |
| `STOCK_UNAVAILABLE` | 필요 재고 부족 |
| `SAFETY_NOT_READY` | 안전 상태가 시작을 허용하지 않음 |
| `ROBOT_UNAVAILABLE` | FR5 명령·상태 경계가 준비되지 않음 |
| `INTERNAL_ERROR` | 분류되지 않은 내부 오류 |

## 4. ROS-ASM-004 상태 조회

### 4.1 기본 명세

| 항목 | 내용 |
| --- | --- |
| 목적 | 활성 작업 또는 최근 terminal snapshot을 조회한다. |
| 호출자 | Unity `RealAssemblyScenarioControl`, MainServer `AssemblyGateway` |
| 제공자 | AssemblySequencer Real adapter |
| 구분 | ROS 2 Service |
| 인터페이스 | `/real/assembly/status` |
| 타입 | `real_assembly_interfaces/srv/GetAssemblyStatus` |
| 상태 | 계약 확정·IDL/실행 노드 미구현 |

### 4.2 요청 필드

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | :---: | --- |
| `job_id` | string | N | 비어 있으면 활성 작업 또는 최근 terminal snapshot 조회 |

### 4.3 응답 필드

| 필드 | 타입·형식 | Nullable | 설명 |
| --- | --- | :---: | --- |
| `found` | bool | N | 조회 결과 존재 여부 |
| `job_id` | string(UUID) | N | Job ID |
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
| `job_id` | string(UUID) | Job ID |
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
| ROS-RBT-009 | `base_link` 기준 Tool 1 TCP 목표 pose | 위치 m, 정규화 가능한 quaternion. 시각화 전용이며 로봇 명령·완료 판정에 사용하지 않음 |

| 공통 규칙 | 내용 |
| --- | --- |
| 완료 판정 | Service 응답만으로 이동·그리퍼 완료를 판정하지 않는다. |
| 변환 | 좌표계와 단위는 각 하위 공개 경계에서 한 번만 변환한다. |
| callback | 로봇 상태 callback에서 DB·MainServer를 호출하지 않는다. |
| 명령 충돌 | 자동 작업 중 수동 명령과 신규 자동 요청을 거절한다. |
| 현장 값 | 좌표계·단위·속도·허용 오차·timeout은 실기 검증 후 기록한다. |

`ROS-RBT-009`는 Real 모드에서만 사용한다. AssemblySequencer 공통 흐름은 Ghost 응답을
기다리지 않으며, `real_assembly` backend가 목표 자세를 확정했을 때 선택적으로 발행한다.
Unity의 `SampleScene > FR5 > RealMaster > RealRobotGhostControl` Inspector에서 MoveIt 또는
FAIRINO SDK IK solver를 선택한다. 두 solver 모두 같은 Tool 1 보정값으로 flange 목표를
계산하며 실제 이동 API를 호출하지 않는다.

### 6.2 타 브랜치 제공 API

아래 계약은 AssemblySequencer가 검증한 YAML workflow와 steps를 조정하고 각 컴포넌트가
검증·좌표 변환·통신·완료 감지·timeout·취소를 완결하기 위한 최소 경계다.

| 대상 브랜치 | 생성·보완할 항목 |
| --- | --- |
| `origin/fr5-robot-control-full` | 신규 ROS API는 만들지 않는다. 기존 `/fairino_remote_command_service`와 `/nonrt_state_data`에서 명령 오류, `robot_motion_done`, `grip_motion_done`, fault·E-STOP 상태를 신뢰할 수 있게 유지한다. |
| `origin/vision-robot-conveyor-control` | 기존 `vision_interfaces` 패키지에 `ResolveAssemblyTargets.action`, `MoveConveyorToStation.action`, `InspectAssembly.action`, `ConveyorState.msg`를 추가하고 아래 endpoint 서버를 구현한다. |
| AssemblySequencer Real adapter | 위 Action client와 FR5 client만 호출한다. 카메라 좌표 변환, 모터 명령, 검사 판정 코드를 중복 구현하지 않는다. |

#### 6.2.1 ROS-VIS-001 Pick·Place 목표 자세 해석

| 항목 | 계약 |
| --- | --- |
| Endpoint | `/vision/pick_place/resolve` |
| Type | `vision_interfaces/action/ResolveAssemblyTargets` |
| 제공자 | Pick/Place Vision |
| 완료 | 모든 Recipe step의 source·target pose가 안정적으로 확정됨 |
| 좌표 | `base_link`, 위치 m, 정규화 가능한 quaternion |
| timeout·취소 | 서버가 자체 timeout을 적용하며 취소 시 진행 중 검출을 정리한다. |

`ResolveAssemblyTargets.action` 정의:

```text
# Goal: 배열 index가 YAML steps 순서다.
string job_id
string recipe_version
string[] part_ids
string[] slot_codes
---
bool success
geometry_msgs/PoseStamped[] source_poses
geometry_msgs/PoseStamped[] target_poses
string error_code
string message
---
string stage
uint32 resolved_count
uint32 total_count
string message
```

- Goal의 두 배열은 길이가 같고 비어 있지 않아야 하며 `slot_codes`는 중복될 수 없다.
- 성공 Result의 두 pose 배열 길이는 Goal 길이와 정확히 같아야 한다.
- 카메라 → `base_link` 변환과 calibration 유효성 검사는 이 Action 서버에서 한 번만 수행한다.
- `CALIBRATION_NOT_READY`, `DETECTION_TIMEOUT`, `PART_NOT_FOUND`,
  `TARGET_NOT_FOUND`, `FRAME_TRANSFORM_FAILED`, `CANCELLED`를 구분한다.

#### 6.2.2 ROS-CNV-001·ROS-STA-002 컨베이어 이동

| 항목 | 계약 |
| --- | --- |
| Endpoint | `/conveyor/move_to_station` |
| Type | `vision_interfaces/action/MoveConveyorToStation` |
| 제공자 | Conveyor controller |
| Goal station | `ASSEMBLY` 또는 `INSPECTION` |
| 완료 | 선택한 정지선 도달 후 실제 정지 상태 확인 |
| 현장 설정 | 속도, 방향, timeout과 정지 보정은 서버 설정이 소유한다. |
| 취소 | 즉시 0속도 명령을 내리고 정지 확인 후 Canceled로 마감한다. |

`MoveConveyorToStation.action` 정의:

```text
string job_id
string station
---
bool success
string reached_station
string error_code
string message
---
string state
string message
```

지속 상태는 `/conveyor/state`에 Reliable, Transient Local, depth 1로 발행한다.

`ConveyorState.msg` 정의:

```text
std_msgs/Header header
string station
string state
bool ready
string error_code
string message
```

- `state`는 `IDLE`, `MOVING`, `STOPPED`, `FAULT`만 사용한다.
- 비전 stop trigger 수신이나 0속도 publish만으로 Action 성공을 반환하지 않는다.
- `NOT_READY`, `SENSOR_TIMEOUT`, `MOTION_TIMEOUT`, `MOTOR_FAULT`,
  `CANCELLED`를 구분한다.
- 기존 one-shot `conveyor_controller` CLI는 수동 시험용으로 유지할 수 있지만
  AssemblySequencer는 Action만 호출한다.

#### 6.2.3 ROS-INS-001 조립 검사

| 항목 | 계약 |
| --- | --- |
| Endpoint | `/vision/inspection/run` |
| Type | `vision_interfaces/action/InspectAssembly` |
| 제공자 | Inspection Vision |
| 완료 | 안정된 검사 결과와 증적 image path가 확정됨 |
| PASS·FAIL | 둘 다 정상 검사 결과이며 `success=true`다. 통신·검사 불능만 `success=false`다. |
| 취소 | 진행 중 캡처·추론을 정리하고 Canceled로 마감한다. |

`InspectAssembly.action` 정의:

```text
string job_id
int64 unit_id
string product_code
string product_version
string recipe_version
---
bool success
string result
string[] slot_codes
string[] defect_types
string image_path
builtin_interfaces/Time inspected_at
string error_code
string message
---
string stage
float32 progress
string message
```

- `result`는 `PASS` 또는 `FAIL`이다. PASS면 defect 배열은 비어 있어야 한다.
- FAIL이면 `slot_codes`와 `defect_types` 길이가 같고 각 slot은 Recipe에 존재해야 한다.
- 기존 `std_srvs/Trigger`와 `Inspection.msg`는 수동 시험·내부 판정에 재사용할
  수 있지만, request 상관관계와 terminal Result가 없으므로 Sequencer 경계로 사용하지 않는다.
- `NO_DETECTION`, `STALE_DETECTION`, `UNSTABLE_RESULT`,
  `INFERENCE_TIMEOUT`, `IMAGE_SAVE_FAILED`, `CANCELLED`를 구분한다.

#### 6.2.4 Safety

Safety 전용 브랜치와 신뢰 가능한 필드가 아직 없으므로 `ROS-SAF-001` endpoint와
Schema는 계속 TBD로 둔다. 물리 E-STOP은 하드와이어드 안전회로가 수행한다.
ROS 2는 상태 전달, 신규 명령 차단과 작업 실패 전환을 담당한다.

## 7. 내부 DB 계약

### 7.1 소유권·권한

| 구분 | 소유자 | 연결 | 권한 |
| --- | --- | --- | --- |
| 생산 조회·Job 생성 | MainServer | `MAIN_SERVER_DB_DSN` | 제품·Job SELECT, `production.jobs` INSERT |
| Job claim·생산 쓰기 | AssemblySequencer | `PRODUCTION_DB_DSN` | `production` transaction |

### 7.2 내부 인터페이스

| ID | 기능명 | 송신자 → 수신자 | 구분 | 상태 |
| --- | --- | --- | --- | --- |
| INT-DB-000 | 조립 Job 전달·claim | 호출자 → AssemblySequencer → PostgreSQL | UUID Job handoff | Mock 구현 |
| INT-DB-001 | 생산 DB 갱신 예약 | Sequencer 업무 흐름 → DB Worker | bounded in-process queue | Mock·공통 구현 |
| INT-DB-002 | 생산 DB transaction 적용 | DB Worker → PostgreSQL | DB transaction | Mock·공통 구현 |

### 7.3 이벤트 처리

| 이벤트 | ProductionStore 처리 |
| --- | --- |
| `ASSEMBLY_COMPLETED` | `complete_assembly_and_consume_stock(unit_id)` |
| `INSPECTION_RECORDED` | `record_inspection(unit_id, result, defects, image_path)` |
| `JOB_FINISHED` | `finish_job(job_id, final_status)` |

| `DbUpdateEvent` 필드 | 설명 |
| --- | --- |
| `event_type` | DB 갱신 종류 |
| `job_id`, `unit_id` | 작업 식별자 |
| `payload` | Store 호출에 필요한 데이터, Raw SQL 금지 |
| `last_error` | 최근 오류 |

### 7.4 Queue 정책

| 항목 | 정책 |
| --- | --- |
| callback | 상태 확정 후 이벤트를 enqueue하고 즉시 반환한다. SQL을 실행하거나 DB 응답을 기다리지 않는다. |
| 순서 | 한 작업의 순서를 보장하는 bounded FIFO·단일 Worker를 우선 사용한다. |
| 제거 | PostgreSQL commit 성공 후에만 제거한다. 검사 callback이 제거하지 않는다. |
| 실패 | backoff 재시도하며 overflow와 최종 실패를 조용히 폐기하지 않는다. |
| 멱등성 | 현재는 ProductionStore의 DB 상태와 transaction 경계로 보장한다. |
| 저장 제외 | 관절·TCP 스트림과 고빈도 상태는 생산 DB에 저장하지 않는다. |
| 영속성 | Job은 `production.jobs`에 영속한다. 완료 이벤트 queue(`DbWriter`)는 프로세스 재시작을 넘는 보존을 보장하지 않는다. |

## 8. 실 로봇 구현자 준수사항

| 구분 | 지켜야 할 내용 |
| --- | --- |
| 공개 계약 | endpoint·필드·상태·terminal 의미를 변경하지 않는다. 변경은 Unity 담당자와 먼저 합의한다. |
| 상관관계 | 모든 비동기 결과를 UUID `job_id`로 활성 작업과 대조한다. 다른 요청의 callback은 폐기한다. |
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
| 같은 `job_id` 재호출 | 새 Job 미생성 |
| 동시 HTTP 요청 | 한 건만 `RUNNING`, 나머지는 `PENDING` 유지 |
| MainServer 종료 | 이미 수락된 작업 계속 실행 |
| DB claim·예약·재고 검증 실패 | 실제 로봇 미동작 |
| DB 지연 | 로봇·안전 callback 정상 처리 |
| DB 복구 | pending 이벤트 순서 적용, commit 후 제거 |
| FR5·Conveyor·Inspection timeout | terminal `FAILED` 전달 |
| E-STOP | 신규 명령 차단, 활성 작업 실패 전환 |
| 정상 작업 | 실제 조립·검사 완료 후에만 `COMPLETED` 발행 |

## 10. 미확정·현재 범위 밖

| 항목 | 상태 |
| --- | --- |
| Safety endpoint·Schema·QoS, 장비별 현장 timeout·보정값 | 담당자 합의 필요 |
| 조립 취소·일시정지·재개 API | 계약 합의 전 미구현 |
| 완료 이벤트의 프로세스 재시작을 넘는 PostgreSQL Outbox | 현재 범위 밖 |
| SECS/GEM·GEM300 Adapter | 현재 범위 밖 |
| 다중 작업 병렬 실행 | 현재 범위 밖 |
| 별도 DB Writer 서버·메시지 브로커 | 현재 범위 밖 |

## Mock 컨베이어 시작 게이트

Mock의 `/unity/assembly/start` 서비스는 기존 `start` 요청을 수락하면 `CONVEYOR_MOVING` feedback을 발행하고, Unity의 `conveyor_arrived` 요청을 받을 때까지 내부 Robot Runner를 시작하지 않는다. Unity는 컨베이어 이동 실패·취소·timeout 시 같은 `job_id`와 `message`를 포함한 `conveyor_failed`를 보내며, Sequencer는 해당 Unit과 Job을 `FAILED`로 마감한다. Unity 프로세스 중단처럼 완료 신호 자체가 사라진 경우에도 Sequencer는 60초 뒤 `CONVEYOR_FAILED`로 마감한다. `conveyor_arrived`는 `{command, job_id}`를 사용한다. `conveyor_failed`는 비어 있지 않은 `message`를 추가로 요구한다.

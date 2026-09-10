# Assembly Sequencer ROS API

이 문서는 현재 구현된 Assembly Sequencer public ROS 2 경계를 설명합니다. 기준 원본은 `sequencer_node.py`의 endpoint 생성과 `recipe_contract.py`의 JSON 검증입니다.

## 가용 범위

공통 Sequencer는 모드별 ROS domain에서 같은 service와 feedback 형식을 사용합니다.
Mock 자동조립은 YAML 실행 경로를 사용합니다. Real은 등록된 Job과 새 현장 확인으로
컨베이어 조립 위치 이동 → 로봇 전체 Start → 컨베이어 검사 위치 이동 → 검사를 실행합니다.
준비 상태 조회에서 `available`·`equipment_ready`는 장비 계약과 설정 검증 결과입니다.
진단 `check_completed`나 Start 수락을 전체 조립 완료로 사용하지 않습니다.

내부 `/mock_db_mvp/internal/*` service와 topic은 Sequencer와 Mock runner 사이의 구현 세부사항이므로 public API에 포함하지 않습니다.

## API 목록

| 범위 | 구분 | Endpoint | ROS type | 방향 |
|---|---|---|---|---|
| Mock / Real | Service | `/unity/assembly/start` | `fairino_msgs/srv/RemoteCmdInterface` | UnityDT·MainServer → Sequencer |
| Mock / Real | Topic | `/unity/assembly/feedback` | `std_msgs/msg/String` | Sequencer → UnityDT |

Service는 모드 접두사와 요청 JSON을 `cmd_str`, 응답 JSON을 `cmd_res`에 넣습니다. 접두사 규칙은 실행 모드 검증 절을 따릅니다. Feedback topic은 JSON을 `data`에 넣으며 queue depth는 10입니다.

## Real에서 소비하는 설비 API

아래는 `real_backend.py`가 실제 사용하는 외부 경계입니다. 코드의 주소·schema·대기 시간 선언 원본은 `api_contracts.py`이며 실제 호출은 이 선언을 참조합니다. Sequencer가 제공하는 API와 구분하며, 제공자 전체 API 목록을 뜻하지 않습니다.

| 제공자 | Endpoint | 타입·방식 | 사용 목적 |
|---|---|---|---|
| 로봇 | `/real/robot/status` | `std_srvs/srv/Trigger` | AUTO·정지·오류·복구·파지 상태 조회 |
| 조립 실행기 | `/real/assembly/status` | `std_srvs/srv/Trigger` | 생산 v2 준비·진행·결과 조회 |
| 조립 실행기 | `/real/assembly/command` | `std_msgs/msg/String`, 발행 | `assembly.start`, `assembly.pause`, `assembly.resume`, `assembly.cancel` |
| 조립 실행기 | `/real/assembly/event` | `std_msgs/msg/String`, 구독 | 실행 ID가 일치하는 진행·종료 수신 |
| 컨베이어 | `/conveyor/state` | `std_msgs/msg/String`, 구독 | 상태 freshness·이동·도착 확인 |
| 컨베이어 | `/conveyor/move_to_assembly` | `std_srvs/srv/Trigger` | 조립 위치 이동 요청 |
| 컨베이어 | `/conveyor/move_to_inspection` | `std_srvs/srv/Trigger` | 검사 위치 이동 요청 |
| 컨베이어 | `/conveyor/stop` | `std_srvs/srv/Trigger` | 이동 오류 이후 정지 요청 |
| Vision | `/api/v1/inspections` | HTTP POST | Job·Unit·검사 ID로 검사 요청 |
| Vision | `/api/v1/inspections/{inspection_id}` | HTTP GET | 동일 검사 진행·결과 조회 |
| Vision | 검사 결과의 `image.path` | HTTP GET | 제공 origin에서 결과 이미지 조회·검증 |

ROS 서비스 응답 한도는 5초입니다. 컨베이어 도착 대기는 35초, 상태 수신 freshness는 1초입니다. 로봇 전체 완료 대기는 1800초이며 2초마다 status로 보완합니다. Vision은 기본 전체 330초·개별 요청 10초 한도를 사용합니다. HTTP 인증은 서버 환경의 Bearer 토큰을 사용하며 문서·로그에 값을 남기지 않습니다.

컨베이어 Trigger에는 Job·Unit을 전송하지 않습니다. `operation_id`는 Sequencer 내부 공정 식별자이며 제공자의 `motion_id`와 동일하지 않습니다. 현재 구현은 매번 새 이동을 요청하고 수락된 motion_id의 도착을 기다립니다. 이미 목적지인 상태의 재사용, 외부 이동의 현재 Job·Unit 연결, 도착의 명령 속도 0 검증은 구현되어 있지 않습니다. `ASSEMBLY_STOP`만으로 새 Unit의 도착 완료를 확정하지 않습니다.

`/real/robot/control`과 개별 MoveJoint·Pick·Place API는 이 경로에서 사용하지 않습니다. 생산 제어는 중첩 production v2 capability를 기준으로 하며 진단 v1의 저수준 제어 capability와 구분합니다.

## Service 명령

| `command` | 필수 데이터 | 의미 |
|---|---|---|
| `status` | 없음 | 활성 작업 또는 최근 terminal snapshot 조회 |
| `start` | `job_id`, `recipe_version`, `scene_confirmation` | Real 전용: 등록된 Job의 실행 준비 검증과 실행 요청 |
| `observations` | `job_id`, `recipe_version`, `observations` | 현재 Scene의 부품·슬롯 좌표 등록 |
| `conveyor_arrived` | `job_id`, `unit_id`, `operation_id` | 조립 위치 도착 확인 후 workflow 재개 |
| `conveyor_failed` | `job_id`, `unit_id`, `operation_id`, `message` | 진행 중 컨베이어 실패 전달 |
| `transfer_assembled_pcb` | `job_id`, `unit_id`, `operation_id`, `assembled_pcb` | 검사 위치 이송 좌표 등록과 workflow 재개 |
| `pause` | `job_id` | 활성 작업 일시정지 요청 |
| `resume` | `job_id` | 활성 작업 재개 요청 |
| `cancel` | `job_id` | 로봇 조립 중 작업 취소 요청 (Real) |

`observations`, `conveyor_arrived`, `conveyor_failed`, `transfer_assembled_pcb`는 Mock 전용입니다.
Real은 이 명령들을 `INVALID_REQUEST`로 거절하며 Unity 신호를 물리 설비 완료로 사용하지 않습니다.
Mock에서는 `start`를 거절하고 기존 observations와 영속 Job 결합 방식을 유지합니다.
`pause`·`resume`·`cancel`은 활성 Job과 대조합니다. Real에서는 로봇 조립 중 production v2 제어로 전달하며 컨베이어 이동·검사 단계에서는 거절합니다. 일시정지는 `after_dispatched_motion` 방식입니다. 제어마다 새 `control_id`와 증가하는 `control_sequence`를 사용하고 재개에는 확인된 `pause_control_id`를 포함합니다.

응답 성공은 요청 전달이며 완료가 아닙니다. status의 `control_pending`이 해제되고 해당 제어 ID와 실제 상태가 일치해야 완료입니다. pause는 `paused`·`stop_verified=true`·`resume_available=true`, resume은 `running`, cancel은 `cancelled`·`stop_verified=true`·`recovery_required=false`를 확인합니다. 취소 완료는 Job `CANCELLED`와 Unit 실패로 기록하고, 기존 상태 계약의 `FAILED`·`EXECUTION_CANCELLED`로 반환합니다. 제어 거절·60초 확인 만료는 `CONTROL_UNCONFIRMED`이며 실제 실행을 완료 처리하지 않습니다. Mock 취소는 미지원입니다.

알 수 없는 필드와 누락된 필드는 `INVALID_REQUEST`입니다. `job_id`는 UUID 문자열이며 status를 제외한 모든 명령에서 현재 Job과 대조합니다.

### status

요청:

```json
{"command": "status"}
```

응답:

```json
{
  "available": true,
  "active": true,
  "job_id": "12345678-1234-5678-1234-567812345678",
  "unit_id": 42,
  "recipe_version": "assembly-r1",
  "state": "PLACED",
  "placed_count": 1,
  "placed_slot_codes": ["SLOT-01"],
  "expected_step_count": 28,
  "held_step_order": 0,
  "held_part_id": "",
  "held_slot_code": "",
  "error_code": "",
  "message": "",
  "db_sync_state": "SYNCED"
}
```

`available=false`면 backend 상태를 조회할 수 없음을 뜻합니다. `active=false`는 실행 중인 작업이 없거나 snapshot이 terminal 상태임을 뜻합니다.

`placed_slot_codes`는 현재 Unit에서 배치가 확인된 슬롯을 실행 순서대로 나열하며 길이는
`placed_count`와 같습니다. 다음 Unit에서는 빈 목록으로 시작합니다. Unity는 이 목록과
`held_slot_code`로 화면을 복구하며 Scene 배열 순서로 배치 위치를 추정하지 않습니다.
전체 레시피나 DB checkpoint는 전달·저장하지 않습니다.

### start (Real)

`real`과 실제 LF 뒤에 아래 JSON을 보냅니다.

```json
{"command":"start","job_id":"12345678-1234-5678-1234-567812345678","recipe_version":"assembly-r1","scene_confirmation":{"operator_id":"operator-1","execution_id":"87654321-4321-8765-4321-876543218765","confirmed_unix":1789000000.0,"scope":"empty_gripper_empty_pcb_full_tray_fixed_fixture"}}
```

예시 시각은 재사용하지 않습니다. `scene_confirmation`은 운영자의 실제 확인 시각을 담아야 하며
미래 시각이 아니고 120초 이내여야 합니다. `operator_id`는 공백이 아닌 최대 128자,
`execution_id`는 새 UUID입니다. 확인 누락은 `NOT_READY`, 잘못된 형식은 `INVALID_REQUEST`입니다.

이 요청은 Job을 생성하지 않습니다. `assembly-r1`의 제품·버전·25개 슬롯을 DB와 대조하고,
로봇 생산 v2 Start 지원·준비 상태와 준비 레시피 revision을 확인한 뒤 Unit을 claim합니다.
로컬 Mock YAML은 사용하지 않습니다. 준비 실패는 Job을 FAILED로 만들지 않습니다.
PENDING Job은 현장 확인 없이 자동 실행하지 않습니다.

동일 활성 실행 ID는 새 조립을 만들지 않습니다. 현재 Unit이 끝나기 전 다른 실행 ID는 `BUSY`입니다.
Start 이후에는 동일 Unit·실행 ID의 전체 완료를 검증한 뒤에만 검사 위치로 이동합니다.
검사 PASS/FAIL은 Unit 완료를 기록하며 PASS만 목표 수량에 포함됩니다. 다음 Unit이 필요하면
`PAUSED`·`SCENE_CONFIRMATION_REQUIRED`로 기다리고 같은 Job에 새 실행 ID와 현장 확인을 받습니다.
검사 `UNKNOWN`은 `PAUSED`·`INSPECTION_UNKNOWN`으로 RUNNING Unit을 유지하며 일반 resume을 거절합니다.
복구가 필요한 실패·불명확한 완료도 PAUSED로 유지하고 다음 공정을 실행하지 않습니다.

대기 상태에는 `state=IDLE`, `active=false`, 빈 Job ID와 `unit_id=0`이 들어갑니다.
활성·terminal snapshot은 실제 Job·Unit과 진행·오류·DB 동기 상태를 제공합니다.
대기 준비 조회의 원격 상태는 `robot_api_status`와 `production_contract`에 포함됩니다.
생산 Start 지원은 중첩 `production_contract.schema=fr5.assembly_execution/v2`와
`capabilities.start=true`로 확인하며 최상위 진단 v1과 구분합니다.


### observations

```json
{
  "command": "observations",
  "job_id": "12345678-1234-5678-1234-567812345678",
  "recipe_version": "assembly-r1",
  "observations": [
    {
      "order": 1,
      "part_id": "PART-01",
      "slot_code": "SLOT-01",
      "source": {
        "xyz_mm": [100.0, 200.0, 300.0],
        "xyzw": [0.0, 0.0, 0.0, 1.0]
      },
      "target": {
        "xyz_mm": [400.0, 500.0, 600.0],
        "xyzw": [0.0, 0.0, 0.0, 1.0]
      }
    }
  ]
}
```

- `order`는 관측 배열 안에서 1부터 연속되는 번호이며 조립 실행 순서가 아닙니다.
- `slot_code`는 연결된 Scene 슬롯 Transform의 이름이며 대소문자를 포함해 YAML과 정확히 일치해야 합니다.
- 슬롯 누락·중복·추가와 슬롯별 `part_id` 불일치는 `INVALID_REQUEST`입니다.
- Mock Sequencer는 `slot_code`로 좌표를 연결하고 고정된 YAML step 순서대로 실행합니다.
- Unity는 각 슬롯에 보낸 source의 공급 부품을 집고, 배치 완료 feedback의 `slot_code`로 snap 대상을 찾습니다.
- `xyz_mm`는 유한한 숫자 3개, `xyzw`는 0이 아닌 유한한 숫자 4개입니다.
- Sequencer는 quaternion을 정규화합니다.
- 좌표 등록만으로 Job을 실행하지 않습니다. 같은 `job_id`의 실행 가능한 DB Job과 backend 준비가 확인돼야 claim합니다.
- 관측과 레시피 대조는 요청 수락·Job claim·첫 설비 동작 전에 완료합니다.
- `slot_code`가 없는 이전 요청은 거절합니다. Unity와 Sequencer를 함께 갱신해야 하며,
  `placed_slot_codes`가 없는 이전 status로는 Unity가 화면을 복구하지 않습니다.

### conveyor 명령

도착:

```json
{"command": "conveyor_arrived", "job_id": "12345678-1234-5678-1234-567812345678", "unit_id": 42, "operation_id": "87654321-4321-8765-4321-876543218765"}
```

실패:

```json
{
  "command": "conveyor_failed",
  "job_id": "12345678-1234-5678-1234-567812345678",
  "unit_id": 42,
  "operation_id": "87654321-4321-8765-4321-876543218765",
  "message": "conveyor stopped before the station"
}
```

`conveyor_arrived`는 상태가 `CONVEYOR_MOVING`일 때만 유효합니다. `conveyor_failed`는 컨베이어 완료를 기다리는 상태에서만 유효하며 `message`는 비어 있지 않아야 합니다.

컨베이어 관련 세 명령은 양의 정수 `unit_id`와 UUID 문자열 `operation_id`를 요구합니다.
Sequencer가 이동마다 새 UUID를 부여하고 `CONVEYOR_MOVING`·`ASSEMBLY_COMPLETED`
feedback과 활성 status의 `operation_id`로 전달합니다. Unity는 이동 시작 시 받은
`job_id`, `unit_id`, `operation_id`를 보관해 응답하며 완료 시점의 현재 식별자로 바꾸지 않습니다.
status의 `operation_id`는 가장 최근 컨베이어 이동을 식별하며, 새 이동에서는 교체됩니다.
이 필드만으로 이동 대기 여부를 판단하지 않고 `state`와 함께 해석해야 합니다.

필드 누락·형식 오류는 `INVALID_REQUEST`, 현재 Job·Unit·이동 불일치는 `NOT_ACTIVE`입니다.
같은 이동의 중복 도착·이송 요청은 완료를 재적용하지 않습니다. 이미 완료되거나
실패·timeout 처리된 대기에 대한 실패 신호는 `BUSY`로 거절합니다.
timeout 이후 도착은 대기를 성공으로 되돌리지 못합니다.
이전 식별자 없는 클라이언트는 지원하지 않으므로 Unity와 Sequencer를 함께 갱신해야 합니다.

### assembled PCB 이송

```json
{
  "command": "transfer_assembled_pcb",
  "job_id": "12345678-1234-5678-1234-567812345678",
  "unit_id": 42,
  "operation_id": "87654321-4321-8765-4321-876543218765",
  "assembled_pcb": {
    "source": {
      "xyz_mm": [100.0, 200.0, 300.0],
      "xyzw": [0.0, 0.0, 0.0, 1.0]
    },
    "target": {
      "xyz_mm": [400.0, 500.0, 600.0],
      "xyzw": [0.0, 0.0, 0.0, 1.0]
    }
  }
}
```

이 명령은 상태가 `ASSEMBLY_COMPLETED`일 때만 유효합니다.

## 일반 Service 응답

status 이외의 명령은 다음 형식을 반환합니다.

```json
{
  "accepted": true,
  "job_id": "12345678-1234-5678-1234-567812345678",
  "error_code": "",
  "message": ""
}
```

`accepted=true`는 명령이 검증되어 처리 또는 예약됐다는 뜻이며 전체 조립 완료가 아닙니다.

| `error_code` | 의미 |
|---|---|
| `NOT_READY` | 실행 준비·설비 계약 미확인, Job claim 전 거절 |
| `INVALID_REQUEST` | JSON, 필드, UUID, 좌표 또는 레시피 버전 오류 |
| `NOT_ACTIVE` | Job이 terminal이거나 현재 활성 Job·Unit·컨베이어 이동과 다름 |
| `BUSY` | 현재 상태에서 명령을 받을 수 없음 |
| `DB_ERROR` | Job 조회·정리 실패 |
| `INTERNAL_ERROR` | backend 요청 또는 내부 처리 실패 |
| `CONTROL_REJECTED` | 생산 제어 요청 전 검증 또는 전달 실패 |
| `CONTROL_UNCONFIRMED` | 제어 거절·시간 초과로 실제 상태 미확인 (status) |
| `EXECUTION_CANCELLED` | 실제 취소 확인 후 생산 취소 반영 |

## Feedback topic

모든 feedback은 Sequencer가 부여한 `unit_id`를 포함합니다. Unit 생성 전 실패는 `0`입니다. Unity는 `(job_id, unit_id)`로 기판 인스턴스와 중복 수신을 구분합니다.

메시지 형식:

```json
{
  "job_id": "12345678-1234-5678-1234-567812345678",
  "unit_id": 42,
  "state": "PLACED",
  "step_order": 1,
  "part_id": "PART-01",
  "slot_code": "SLOT-01",
  "error_code": "",
  "message": "",
  "db_sync_state": "PENDING"
}
```

| 필드 | 의미 |
|---|---|
| `job_id` | 진행·결과를 대조하는 UUID |
| `unit_id` | 현재 생산 시도의 ID, Unit 생성 전 실패는 0 |
| `operation_id` | `CONVEYOR_MOVING`·`ASSEMBLY_COMPLETED`에 포함되는 이동 UUID |
| `state` | 실행 상태 |
| `step_order` | 해당 step 순서, step이 없으면 0 |
| `part_id`, `slot_code` | Pick·Place 대상, 해당 없으면 빈 문자열 |
| `error_code`, `message` | 실패 원인, 정상 상태면 빈 문자열 |
| `db_sync_state` | 생산 기록 동기화 상태 |

생산 기록의 영구 오류 또는 동기화 대기 한도(5초) 초과 시
`db_sync_state=FAILED`를 유지하고 후속 생산을 차단한다.
이때 실행 실패 피드백은 DB의 Job·Unit 상태까지 `FAILED`로 저장됐다는 뜻이 아니다.
이미 전달된 트랜잭션의 늦은 반영 가능성이 있으므로 DB 복구 후 Sequencer를
재시작하고 기존 Unit 복구 및 설비 준비·reset 확인 절차를 따른다.

실행 상태:

| 상태 | 의미 | Terminal |
|---|---|:---:|
| `CONVEYOR_MOVING` | 조립 위치 도착 확인 대기 | N |
| `STARTED` | backend 실행 시작 | N |
| `PICKED` | 부품 Pick 완료 | N |
| `PLACED` | 부품 Place 완료 | N |
| `ASSEMBLY_COMPLETED` | 조립 완료 후 검사 위치 이동·검사 진행; Mock에서는 PCB 이송 요청 대기 | N |
| `PCB_PICKED` | 조립 PCB Pick 완료 | N |
| `PCB_PLACED` | 조립 PCB Place 완료 | N |
| `PAUSED` | 일시정지 확인 또는 오류·현장 확인·검사 판정 보류; error_code와 함께 해석 | N |
| `COMPLETED` | 목표 PASS 수량 생산 완료 | Y |
| `FAILED` | 실행 또는 기록 실패 | Y |

`PICKED`와 `PLACED`는 양의 `step_order`, 비어 있지 않은 `part_id`와 `slot_code`를 요구합니다.

DB 동기화 상태는 `NOT_STARTED`, `PENDING`, `SYNCED`, `FAILED` 중 하나입니다. `FAILED` feedback의 오류 코드는 하위 backend 또는 Sequencer가 확정한 원인을 전달하며 호출자는 문자열을 그대로 보존해야 합니다.

## 실행 모드 검증

선택된 service의 `cmd_str`는 실제 LF를 포함한 `mock\n` 또는 `real\n` 접두사 뒤에 해당 모드의 JSON payload를
전달합니다. 접두사 누락·불일치는 `accepted=false`, `error_code=MODE_MISMATCH`이며
DB·실행 함수를 호출하지 않습니다. 읽기 요청 `{"command":"status"}`는 접두사 없이도
허용하며 상태 응답의 `runtime_mode`는 선택된 모드입니다. 내부 Mock backend도 접두사를 검사합니다.
`ASSEMBLY_SEQUENCER_MODE`는 시작 시 고정되며 Mock/domain 42, Real/domain 5 조합만 허용합니다.
DB는 같은 모드의 관리자 설정을 확인하고 실행 중 모드 변경을 거절합니다. 도메인은 인증 수단이 아닙니다.

검사 결과 `UNKNOWN`은 자료 저장·flush 후 `PAUSED`와 `INSPECTION_UNKNOWN`으로 표시합니다.
Job·Unit은 RUNNING을 유지하고 기판 이송·다음 Unit·일반 resume는 진행하지 않습니다.
검사 판정 해소·재검사 API는 제공하지 않습니다.

### 진행 설명 표시

Real 실행의 `message`는 컨베이어 목적지 이동, 로봇이 보고한 `current_stage`, 검사 진행과
확인된 검사 결과를 전달합니다. 로봇 단계가 바뀌면 완료 슬롯 증가가 없어도 feedback을 발행하며,
같은 완료 슬롯 목록·단계의 반복 callback은 추가 발행하지 않습니다. status에도 최신 설명을 보존합니다.
`message`는 표시용 설명이며 설비 제어 명령이나 완료 판정의 근거가 아닙니다.
후속 촬영 단계는 검사 PASS가 아니며, 검사 FAIL 이후 새 PCB 확인 대기와 UNKNOWN 판정 보류는
기존 `PAUSED` 상태와 오류 의미를 유지합니다. Real Unity는 feedback 수신 후 status를 조회합니다.

Real status의 선택적 표시 필드 `current_part_id`, `current_slot_code`, `current_action`,
`current_phase`, `current_event`는 로봇 callback의 현재 대상과 마지막 세부 동작 이벤트입니다.
현재 실행 ID와 생산 슬롯·부품에 일치하는 context만 표시하며, 해당 context 변경도 feedback으로
상태 재조회를 알립니다. `PHASE_STARTED`는 진행 중, `PHASE_COMPLETED`는 해당 단계 완료,
`OPERATION_COMPLETED`는 해당 동작 완료이며 전체 생산 완료나 물리 파지·품질 검증을 뜻하지 않습니다.
촬영·컨베이어·검사·종료 상태에는 빈 문자열을 반환하며, 미지원 제공자의 필드 누락은 상세 정보 없음입니다.
`held_*`의 파지 의미, 기존 feedback `part_id`·`slot_code`와 완료 판정은 변경하지 않습니다.

### 검사 불량의 생산 대기

검사 FAIL Unit의 완료와 `jobs.job_status=PAUSED`를 함께 저장한 뒤,
기존 status/feedback에 `state=PAUSED`, `error_code=QUALITY_HOLD`를 반환합니다.
다른 Unit·Job을 자동으로 시작하지 않으며 재시작 시 DB에서 대기를 복원합니다.
기존 `resume`은 불량 대기를 해제합니다. Real은 설비 준비 확인 후
`SCENE_CONFIRMATION_REQUIRED`로 전환하고 새 현장 확인을 포함한 `start`를 기다립니다.
Mock은 기존 다음 Unit 흐름을 재개합니다. Real의 `cancel`은 해당 Job을 CANCELLED로
종료하며 완료된 로봇 실행에 제어 명령을 보내지 않습니다. 취소 이후 영속적인 라인 잠금은 제공하지 않습니다.
이 분기는 관리자 인증이나 결정 이력을 추가하지 않으며 기존 버튼의 권한 체계를 따릅니다.

### 조립 전 보류 작업 취소

Real에서 로봇 Start 전 `PAUSED`인 활성 Job은 기존 `cancel`로 취소할 수 있습니다. 접수 후 비동기로 컨베이어 stop을 요청하고, 요청 이후 새로 수신한 동일 서버의 상태가 freshness 한도 안에서 `moving=false`·명령 속도 0·정지 상태임을 확인합니다. 비전의 이동 준비 여부는 정지 확인 조건이 아닙니다. 정지 확인 후에만 기존 DB 종료 경로로 Job `CANCELLED`와 진행 Unit의 실패를 반영합니다. 기록·재고를 삭제하거나 복원하지 않습니다.

처리 중 중복 cancel은 같은 처리를 기다립니다. 정지 실패는 `PAUSED`·`CONTROL_UNCONFIRMED`로 남고 재요청할 수 있습니다. DB 오류는 취소 완료가 아니며 DB 동기 상태를 확인해야 합니다. 최근 취소 terminal snapshot의 동일 Job 재요청은 기존 성공을 반환합니다. 이동 중 취소와 검사 중 취소는 이번 경로에 포함되지 않습니다.

로봇 제어 대기 중 같은 action 재요청은 기존 control_id를 재사용하여 상태 확인을 계속하며 재발행하지 않습니다. 다른 제어가 미확인인 상태에서는 새 제어로 덮어쓰지 않습니다. 원격 실행 추적이 종료된 이후의 복구는 이 재요청 기능으로 해결되지 않습니다.

### 제어 판정과 결과 재확인

Real status는 `controls_available=true`와 `pause_reason`, `resume_reason`, `cancel_reason`을 제공합니다. 각 reason이 빈 문자열이면 해당 조작을 요청할 수 있습니다. 이는 동작 완료 보장이 아니며 실제 요청 시 같은 공정 판정과 장비 검증을 다시 수행합니다. DB 반영 실패·검사 보류·다음 Unit 확인·미확인 제어와 원격 capability·복구 상태를 대조합니다. 원격 제어 상태가 3초 이상 오래되면 조작 허용을 유지하지 않습니다.

실행 대기가 불명확하게 종료돼도 같은 프로세스 안에서는 실행·제어 ID를 보존합니다. status 조회는 동일 서버·실행의 원격 결과를 재확인합니다. control_id가 일치하는 확정 거절만 대기를 해제하며 식별자 없는 거절은 임의 해제하지 않습니다. 공정 추적이 끝난 실행은 자동 재개하지 않고 지원되는 취소만 허용합니다. 실제 취소·정지·DB 반영 이후 연결을 해제합니다. 프로세스 재시작은 기존 Unit 복구 정책을 따르며 이 메모리 추적을 복원하지 않습니다.

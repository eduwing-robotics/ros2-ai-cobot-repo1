# Assembly Sequencer ROS API

이 문서는 현재 구현된 Assembly Sequencer public ROS 2 경계를 설명합니다. 기준 원본은 `sequencer_node.py`의 endpoint 생성과 `recipe_contract.py`의 JSON 검증입니다.

## 가용 범위

공통 Sequencer는 모드별 ROS domain에서 같은 service와 feedback 형식을 사용합니다.
Mock 자동조립은 연결되어 있습니다. Real은 상태 조회와 시작 요청의 검증 경계가 연결되었지만,
설비 실행 경계가 미완성이므로 `start`를 `NOT_READY`로 거절하며 Job claim·이동을 수행하지 않습니다.
Real 상태의 `available`과 `equipment_ready`는 현재 `false`입니다. 이는 노드 통신 실패와 구분됩니다.

내부 `/mock_db_mvp/internal/*` service와 topic은 Sequencer와 Mock runner 사이의 구현 세부사항이므로 public API에 포함하지 않습니다.

## API 목록

| 범위 | 구분 | Endpoint | ROS type | 방향 |
|---|---|---|---|---|
| Mock / Real | Service | `/unity/assembly/start` | `fairino_msgs/srv/RemoteCmdInterface` | UnityDT·MainServer → Sequencer |
| Mock / Real | Topic | `/unity/assembly/feedback` | `std_msgs/msg/String` | Sequencer → UnityDT |

Service는 모드 접두사와 요청 JSON을 `cmd_str`, 응답 JSON을 `cmd_res`에 넣습니다. 접두사 규칙은 실행 모드 검증 절을 따릅니다. Feedback topic은 JSON을 `data`에 넣으며 queue depth는 10입니다.

## Service 명령

| `command` | 필수 데이터 | 의미 |
|---|---|---|
| `status` | 없음 | 활성 작업 또는 최근 terminal snapshot 조회 |
| `start` | `job_id`, `recipe_version` | Real 전용: 등록된 Job의 실행 준비 검증과 실행 요청 |
| `observations` | `job_id`, `recipe_version`, `observations` | 현재 Scene의 부품·슬롯 좌표 등록 |
| `conveyor_arrived` | `job_id` | 조립 위치 도착 확인 후 workflow 재개 |
| `conveyor_failed` | `job_id`, `message` | 진행 중 컨베이어 실패 전달 |
| `transfer_assembled_pcb` | `job_id`, `assembled_pcb` | 검사 위치 이송 좌표 등록과 workflow 재개 |
| `pause` | `job_id` | 활성 작업 일시정지 요청 |
| `resume` | `job_id` | 활성 작업 재개 요청 |

`observations`, `conveyor_arrived`, `conveyor_failed`, `transfer_assembled_pcb`는 Mock 전용입니다.
Real은 이 명령들을 `INVALID_REQUEST`로 거절하며 Unity 신호를 물리 설비 완료로 사용하지 않습니다.
Mock에서는 `start`를 거절하고 기존 observations와 영속 Job 결합 방식을 유지합니다.
`pause`·`resume`은 활성 Job과 대조하며 Real 설비의 해당 동작은 아직 연결되지 않았습니다.

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
{"command":"start","job_id":"12345678-1234-5678-1234-567812345678","recipe_version":"assembly-r1"}
```

이 요청은 Job을 생성하지 않습니다. 현재는 실제 교시·좌표 공급·안전·컨베이어 도착·reset·
수동/자동 명령 소유권 경계가 연결되지 않아 `accepted=false`, `error_code=NOT_READY`를 반환합니다.
이 실패는 DB Job을 `FAILED`로 전이하지 않습니다.
상태 조회에는 `runtime_mode=real`, `command_service_available`, `robot_state_fresh`,
`equipment_ready=false`가 포함되며 개별 통신 정상도 셀 준비 완료를 뜻하지 않습니다.

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
- Sequencer는 `slot_code`로 좌표를 연결하고 고정된 YAML step 순서대로 실행합니다.
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
{"command": "conveyor_arrived", "job_id": "12345678-1234-5678-1234-567812345678"}
```

실패:

```json
{
  "command": "conveyor_failed",
  "job_id": "12345678-1234-5678-1234-567812345678",
  "message": "conveyor stopped before the station"
}
```

`conveyor_arrived`는 상태가 `CONVEYOR_MOVING`일 때만 유효합니다. `conveyor_failed`는 컨베이어 완료를 기다리는 상태에서만 유효하며 `message`는 비어 있지 않아야 합니다.

### assembled PCB 이송

```json
{
  "command": "transfer_assembled_pcb",
  "job_id": "12345678-1234-5678-1234-567812345678",
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
| `NOT_ACTIVE` | Job이 terminal이거나 현재 활성 Job과 다름 |
| `BUSY` | 현재 상태에서 명령을 받을 수 없음 |
| `DB_ERROR` | Job 조회·정리 실패 |
| `INTERNAL_ERROR` | backend 요청 또는 내부 처리 실패 |

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
| `ASSEMBLY_COMPLETED` | 부품 조립 완료, PCB 이송 요청 대기 | N |
| `PCB_PICKED` | 조립 PCB Pick 완료 | N |
| `PCB_PLACED` | 조립 PCB Place 완료 | N |
| `PAUSED` | backend 일시정지 확인 | N |
| `COMPLETED` | 목표 PASS 수량 생산 완료 | Y |
| `FAILED` | 실행 또는 기록 실패 | Y |

`PICKED`와 `PLACED`는 양의 `step_order`, 비어 있지 않은 `part_id`와 `slot_code`를 요구합니다.

DB 동기화 상태는 `NOT_STARTED`, `PENDING`, `SYNCED`, `FAILED` 중 하나입니다. `FAILED` feedback의 오류 코드는 하위 backend 또는 Sequencer가 확정한 원인을 전달하며 호출자는 문자열을 그대로 보존해야 합니다.

## 실행 모드 검증

선택된 service의 `cmd_str`는 실제 LF를 포함한 `mock\n` 또는 `real\n` 접두사 뒤에 해당 모드의 JSON payload를
전달합니다. 접두사 누락·불일치는 `accepted=false`, `error_code=MODE_MISMATCH`이며
DB·실행 함수를 호출하지 않습니다. 읽기 요청 `{"command":"status"}`는 접두사 없이도
허용하며 상태 응답의 `runtime_mode`는 선택된 모드입니다. 내부 Mock backend도 접두사를 검사합니다.
`ASSEMBLY_SEQUENCER_MODE`는 시작 시 고정되며 Mock/domain 42, Real/domain 43 조합만 허용합니다.
DB는 같은 모드의 관리자 설정을 확인하고 실행 중 모드 변경을 거절합니다. 도메인은 인증 수단이 아닙니다.

검사 결과 `UNKNOWN`은 자료 저장·flush 후 `PAUSED`와 `INSPECTION_UNKNOWN`으로 표시합니다.
Job·Unit은 RUNNING을 유지하고 기판 이송·다음 Unit·일반 resume는 진행하지 않습니다.
검사 판정 해소·재검사 API는 제공하지 않습니다.

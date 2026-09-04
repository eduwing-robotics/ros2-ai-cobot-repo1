# Assembly Sequencer ROS API

이 문서는 현재 구현된 Assembly Sequencer public ROS 2 경계를 설명합니다. 기준 원본은 `mock_node.py`의 endpoint 생성과 `mock_contract.py`의 JSON 검증입니다.

## 가용 범위

현재 public 조립 API는 Mock 구현만 제공합니다. Real 자동 조립 API와 전용 IDL은 구현되어 있지 않으며 이 문서에서 endpoint 이름을 예약하지 않습니다.

내부 `/mock_db_mvp/internal/*` service와 topic은 Sequencer와 Mock runner 사이의 구현 세부사항이므로 public API에 포함하지 않습니다.

## API 목록

| 범위 | 구분 | Endpoint | ROS type | 방향 |
|---|---|---|---|---|
| Mock | Service | `/unity/assembly/start` | `fairino_msgs/srv/RemoteCmdInterface` | UnityDT·MainServer → Sequencer |
| Mock | Topic | `/unity/assembly/feedback` | `std_msgs/msg/String` | Sequencer → UnityDT |

Service는 요청 JSON을 `cmd_str`, 응답 JSON을 `cmd_res`에 넣습니다. Feedback topic은 JSON을 `data`에 넣으며 queue depth는 10입니다.

## Service 명령

| `command` | 필수 데이터 | 의미 |
|---|---|---|
| `status` | 없음 | 활성 작업 또는 최근 terminal snapshot 조회 |
| `observations` | `job_id`, `recipe_version`, `observations` | 현재 Scene의 부품·슬롯 좌표 등록 |
| `conveyor_arrived` | `job_id` | 조립 위치 도착 확인 후 workflow 재개 |
| `conveyor_failed` | `job_id`, `message` | 진행 중 컨베이어 실패 전달 |
| `transfer_assembled_pcb` | `job_id`, `assembled_pcb` | 검사 위치 이송 좌표 등록과 workflow 재개 |
| `pause` | `job_id` | 활성 작업 일시정지 요청 |
| `resume` | `job_id` | 활성 작업 재개 요청 |

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

- `order`는 1부터 연속되어야 합니다.
- `part_id`와 순서는 고정된 레시피 step과 일치해야 합니다.
- `xyz_mm`는 유한한 숫자 3개, `xyzw`는 0이 아닌 유한한 숫자 4개입니다.
- Sequencer는 quaternion을 정규화합니다.
- 좌표 등록만으로 Job을 실행하지 않습니다. 같은 `job_id`의 실행 가능한 DB Job과 backend 준비가 확인돼야 claim합니다.

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
| `INVALID_REQUEST` | JSON, 필드, UUID, 좌표 또는 레시피 버전 오류 |
| `NOT_ACTIVE` | Job이 terminal이거나 현재 활성 Job과 다름 |
| `BUSY` | 현재 상태에서 명령을 받을 수 없음 |
| `DB_ERROR` | Job 조회·정리 실패 |
| `INTERNAL_ERROR` | backend 요청 또는 내부 처리 실패 |

## Feedback topic

메시지 형식:

```json
{
  "job_id": "12345678-1234-5678-1234-567812345678",
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
| `state` | 실행 상태 |
| `step_order` | 해당 step 순서, step이 없으면 0 |
| `part_id`, `slot_code` | Pick·Place 대상, 해당 없으면 빈 문자열 |
| `error_code`, `message` | 실패 원인, 정상 상태면 빈 문자열 |
| `db_sync_state` | 생산 기록 동기화 상태 |

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

# 컨베이어 ROS 2 API 계약

## 환경

- ROS 2 Jazzy
- `ROS_DOMAIN_ID=5`
- Unity ROS-TCP Endpoint: TCP `10000`
- station: `assembly`, `inspection`

## 서비스

모두 `std_srvs/srv/Trigger` 타입이다.

| 서비스 | 설명 |
|---|---|
| `/conveyor/move_to_assembly` | 조립 정지선까지 이동 요청 |
| `/conveyor/move_to_inspection` | 조립 완료 후 검사 정지선까지 이동 요청 |
| `/conveyor/stop` | 즉시 HOLD 및 `MANUAL_STOP` |
| `/conveyor/reset` | 정지 상태를 `IDLE`로 복구하며 이동하지 않음 |

`response.success=true`는 요청 수락이다. 도착은 상태 토픽으로 확인한다.

2026-09-09 보완: 수락 응답에 `motion_id`, 상태에 `motion_id`,
`completed_station`, `arrival={station,motion_id,timestamp_ns,basis}`가 추가되었습니다.
도착 시 `target_station=null`은 기존 규격입니다. `arrival`과 STOP 상태를 사용하고
motion_id별 한 번만 콜백 처리하세요. FAULT/MANUAL_STOP/IDLE은 도착이 아닙니다.
완료 정보는 정지 상태 heartbeat에 유지됩니다. 서버 재시작마다 ID 공간이 달라집니다.

## 제어 상태

| 토픽 | 타입 |
|---|---|
| `/conveyor/state` | `std_msgs/msg/String` JSON, 10 Hz |
| `/conveyor/moving` | `std_msgs/msg/Bool` |

상태 열거형:

```text
IDLE
MOVING_TO_ASSEMBLY
ASSEMBLY_STOP
MOVING_TO_INSPECTION
INSPECTION_STOP
MANUAL_STOP
FAULT
```

상태 JSON schema version 1 예시:

```json
{
  "schema_version": 1,
  "timestamp_ns": 1788430878427605600,
  "state": "ASSEMBLY_STOP",
  "moving": false,
  "target_station": null,
  "reason": "assembly vision stop trigger",
  "armed": true,
  "command_linear_x_mps": 0.0,
  "vision_ready": true,
  "vision_ready_fresh": true,
  "assembly_trigger": true,
  "inspection_trigger": false,
  "fr5_clear": true,
  "fr5_clear_fresh": true,
  "fr5_interlock_required": true
}
```

## 필수 interlock 입력

| 토픽 | 타입 | timeout |
|---|---|---:|
| `/cell/fr5_clear_for_conveyor` | `std_msgs/msg/Bool` | 0.25 s |
| `/vision/conveyor/stop_line_ready` | `std_msgs/msg/Bool` | 0.15 s |
| `/vision/conveyor/{station}/stop_trigger` | `std_msgs/msg/Bool` | 0.15 s |

하나라도 false/stale이면 출발을 거절하거나 이동 중 FAULT 정지한다.

## 비전 관측 토픽

| 토픽 | 타입 | 의미 |
|---|---|---|
| `/vision/conveyor/board_count` | `std_msgs/msg/Int32` | 화면 내 검출 기판 수 수 |
| `/vision/conveyor/station_spacing_valid` | `std_msgs/msg/Bool` | 기판 두 장 간격 안전 여부 |
| `/vision/conveyor/{station}/board_detected` | `std_msgs/msg/Bool` | station 계산 후보 존재 여부 |
| `/vision/conveyor/{station}/distance_to_stop_px` | `std_msgs/msg/Float32` | 양수=도달 전, 0=표시선, 음수=통과 |
| `/vision/conveyor/{station}/stop_line_normalized` | `std_msgs/msg/Float32` | 영상 폭 기준 0~1 정지선 좌표 |
| `/vision/conveyor/{station}/board_polygon_normalized` | `geometry_msgs/msg/PolygonStamped` | 기판 4점, x/y 각각 0~1 |
| `/vision/conveyor/stop_image/compressed` | `sensor_msgs/msg/CompressedImage` | UI 모니터링 영상 |

`board_detected=true`는 station 도착이 아닙니다. 원격 이동 완료는
`/conveyor/state`의 STOP 상태와 요청 motion_id에 일치하는 arrival을 사용합니다.
원시 trigger 상승 에지는 비전 관측일 뿐 원격 요청 완료와 혼동하지 마세요.

## 안전 경계

- 기본 벨트 전진: TurtleBot `TwistStamped.linear.x=-0.10 m/s`
- 최대 연속 이동: 30초
- 다른 `/cmd_vel` publisher 발견 시 출발 거부/FAULT
- 서버 종료, heartbeat timeout, FR5 clear=false, 비전 trigger에서 0속도 발행
- `/conveyor/state`는 command state이며 encoder 기반 물리 feedback이 아님

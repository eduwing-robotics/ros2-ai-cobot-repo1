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

일반 이동의 `response.success=true`는 요청 수락이다. 도착은 상태 토픽으로 확인한다.
현재 영상으로 같은 목적지 도착이 검증된 재요청은 새 이동 없이
`already_arrived=true, completed=true`를 반환할 수 있다.
새 현재 도착 조회 서비스와 Sequencer 처리 분기는
[현재 도착 확인 보완](CURRENT_ARRIVAL_UPDATE.md)을 따른다.

2026-09-09 보완: 수락 응답에 `motion_id`, 상태에 `motion_id`,
`completed_station`, `arrival={station,motion_id,timestamp_ns,basis}`가 추가되었습니다.
도착 시 `target_station=null`은 기존 규격입니다. `arrival`과 STOP 상태를 사용하고
motion_id별 한 번만 콜백 처리하세요. FAULT/MANUAL_STOP/IDLE은 도착이 아닙니다.
완료 정보는 정지 상태에 유지됩니다. 서버 재시작마다 ID 공간이 달라집니다.

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
  "command_receiver_connected": true,
  "assembly_trigger": true,
  "inspection_trigger": false,
  "fr5_clear": false,
  "fr5_clear_fresh": false,
  "fr5_interlock_required": false
}
```

## 필수 제어 상태 입력

| 토픽 | 타입 | 동작 |
|---|---|---|

| `/vision/conveyor/stop_line_ready` | `std_msgs/msg/Bool` | `false`이면 출발 차단·이동 중 정지 |
| `/vision/conveyor/{station}/stop_trigger` | `std_msgs/msg/Bool` | `true`이면 해당 정지선 HOLD |

Bool의 수신 시각이 오래됐다는 이유만으로 fault를 만들지 않는다. 정지선 검출
오류는 `ready=false`로 명시되고, trigger 상승은 목적지 HOLD를 만든다.

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
- 서버 종료, 명시적인 비전 not-ready/trigger, 유한 이동 timeout에서 0속도 발행
- 이동 요청 전에 호환되는 로봇 `/cmd_vel` subscriber가 없으면 즉시 거절하며,
  수신기 없이 요청을 받아 30초 뒤 timeout으로 끝내지 않는다.
- `/conveyor/state`는 command state이며 encoder 기반 물리 feedback이 아님

FR5 permission input was removed on 2026-09-09. The three legacy FR5 status fields are always false (unavailable, not measured clearance). No FR5 subscription or timeout remains.

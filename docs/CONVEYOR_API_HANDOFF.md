# KSMC Conveyor Integration API Handoff

기준일: 2026-09-03  
대상: DB/Backend, Unity Digital Twin 팀원  
통신: ROS 2 Jazzy (`ROS_DOMAIN_ID=5`), Unity는 ROS-TCP Endpoint 사용

2026-09-08: [컨베이어+Vision 통합 실행기](CONVEYOR_VISION_SERVER.md)를 추가했다.
기존 ROS 서비스 및 Vision HTTP JSON/PNG 계약은 바뀌지 않는다. 기존 서버가 있으면
중복 시작을 거절하며, 팀원 연결을 끊고 강제로 인수하지 않는다.

## 1. 현재 구현 범위

현재 컨베이어 연동 API는 HTTP REST API가 아니라 **ROS 2 토픽·서비스 인터페이스**다.
S22 비전 노드가 기판과 두 정지선을 추적하고, 별도 컨베이어 제어 노드가 선택된
정지선까지 한 번 이동한 후 정지한다.

- station ID: `assembly`, `inspection`
- 구현 완료: 기판 검출, 정지선까지 거리, 정지 trigger, 두 기판 간격 검사,
  원격 station 이동·정지·reset 서비스, FR5-clear heartbeat interlock,
  fail-safe 정지
- 아직 없음: 실제 모터 encoder 상태 feedback, 완성된 생산 cycle ID 관리자,
  FR5 제어 노드의 clear 신호 publisher
- DB와 Unity는 상태를 구독하고 Main Server 정책에 따라 이동 서비스를 호출한다.
- DB/Unity에서 `/cmd_vel`을 직접 발행하지 않는다. 속도 명령 publisher는
  `conveyor_controller` 하나만 사용한다.

## 2. 필수 ROS 환경

ROS 2를 직접 사용하는 컴퓨터는 같은 네트워크와 domain을 사용한다.

```bash
source /opt/ros/jazzy/setup.bash
source ~/KSMC/ros2_ws/install/setup.bash
export ROS_DOMAIN_ID=5
```

연결 확인:

```bash
ros2 topic list | grep /vision/conveyor
ros2 topic echo /vision/conveyor/stop_line_ready
```

## 3. 정식 구독 인터페이스

### 전체 상태

| 토픽 | 타입 | 의미 |
|---|---|---|
| `/vision/conveyor/stop_line_ready` | `std_msgs/msg/Bool` | 정지선 제어 허가 heartbeat. `false` 또는 갱신 중단은 FAULT로 처리 |
| `/vision/conveyor/station_spacing_valid` | `std_msgs/msg/Bool` | 두 정지 위치에 기판 두 장을 둘 수 있는 간격인지 여부 |
| `/vision/conveyor/station_spacing_board_lengths` | `std_msgs/msg/Float32` | 정지선 간격 ÷ 검출 기판 진행축 길이 |
| `/vision/conveyor/board_count` | `std_msgs/msg/Int32` | 현재 S22 화면에서 분리 검출된 기판 수 |
| `/vision/conveyor/stop_image/compressed` | `sensor_msgs/msg/CompressedImage` | 정지선·기판이 표시된 모니터링 영상. 제어 판정용으로 재사용하지 않음 |

### station별 상태

아래 `{station}`은 `assembly` 또는 `inspection`이다.

| 토픽 | 타입 | 의미 |
|---|---|---|
| `/vision/conveyor/{station}/stop_trigger` | `std_msgs/msg/Bool` | 기판 후단이 지연 보정 trigger 경계를 통과하면 `true`로 래치 |
| `/vision/conveyor/{station}/board_detected` | `std_msgs/msg/Bool` | 해당 station 계산에 사용할 기판 후보가 보이는지 여부 |
| `/vision/conveyor/{station}/distance_to_stop_px` | `std_msgs/msg/Float32` | 기판 후단에서 표시 정지선까지 남은 진행 방향 거리. 양수=도달 전, 0=표시선, 음수=통과 |
| `/vision/conveyor/{station}/trailing_edge_px` | `std_msgs/msg/Float32` | 제어 영상에서 검출한 기판 후단 픽셀 좌표 |
| `/vision/conveyor/{station}/stop_line_normalized` | `std_msgs/msg/Float32` | 영상 폭 기준 정지선 좌표(0~1). 값을 코드에 하드코딩하지 말고 구독 |
| `/vision/conveyor/{station}/board_polygon_normalized` | `geometry_msgs/msg/PolygonStamped` | 기판 네 꼭짓점. `x`,`y`는 각각 영상 폭·높이 기준 0~1 |

`board_detected=true`만으로 “정지 위치 도착”이라고 판단하면 안 된다. 화면에 기판이
하나라도 있으면 각 station에 가장 가까운 후보가 계산될 수 있다. 실제 도착 이벤트는
반드시 해당 station의 `stop_trigger` 상승 에지(`false -> true`)를 사용한다.

현재 trigger는 제어 지연을 보정하기 위해 표시선보다 20 px 앞에서 발생한다.
표시 정지선의 현재 설정은 `assembly=0.18301061`, `inspection=0.50520833`이지만,
카메라 재설정 시 바뀔 수 있으므로 연동 코드에서 상수로 고정하지 않는다.

## 4. 원격 제어 서비스

### 서버 실행

모니터 전용으로 API와 상태 형식만 확인할 때:

```bash
~/KSMC/run_conveyor_remote_server.sh --monitor-only
```

원격 이동을 허용할 때:

```bash
~/KSMC/run_conveyor_remote_server.sh --execute --confirm-motion
```

두 번째 명령도 서버 실행만으로는 움직이지 않는다. 아래 이동 서비스가 요청되고
모든 interlock을 통과해야 `/cmd_vel`이 발행된다. 기존 단발 제어 스크립트와 원격
서버를 동시에 실행하지 않으며, 서버도 다른 `/cmd_vel` publisher를 발견하면
이동을 거부하거나 즉시 `FAULT` 정지한다.

### 서비스 규격

모든 서비스 타입은 `std_srvs/srv/Trigger`이고 request body는 비어 있다.

| 서비스 | 동작 |
|---|---|
| `/conveyor/move_to_assembly` | `assembly` 정지선까지 이동 요청 |
| `/conveyor/move_to_inspection` | 조립 정지 확인 후 `inspection` 정지선까지 이동 요청 |
| `/conveyor/stop` | 상태와 무관하게 즉시 0속도 HOLD, 상태를 `MANUAL_STOP`으로 변경 |
| `/conveyor/reset` | `FAULT`/`MANUAL_STOP`을 `IDLE`로 복구. 이동은 시작하지 않음 |

호출 예시:

```bash
ros2 service call /conveyor/move_to_assembly std_srvs/srv/Trigger '{}'
ros2 service call /conveyor/move_to_inspection std_srvs/srv/Trigger '{}'
ros2 service call /conveyor/stop std_srvs/srv/Trigger '{}'
ros2 service call /conveyor/reset std_srvs/srv/Trigger '{}'
```

응답의 `success=false`는 명령을 실행하지 않았다는 뜻이며 `message`에 거절 이유가
들어 있다. `success=true`인 이동 응답은 “이동 명령 수락”이지 물리 도착 완료가
아니다. 완료는 `/conveyor/state`와 station trigger로 확인한다.

### 필수 FR5 interlock 입력

| 토픽 | 타입 | 의미 |
|---|---|---|
| `/cell/fr5_clear_for_conveyor` | `std_msgs/msg/Bool` | FR5와 그리퍼가 컨베이어 작업영역 밖에 있으면 `true` |

FR5/Main Server 담당 노드는 이 토픽을 최소 10 Hz로 계속 발행해야 한다. 신호가
`false`이거나 250 ms 이상 끊기면 출발 요청을 거부하고, 이동 중이면 즉시
`FAULT`와 0속도를 발행한다. 아직 실제 FR5 clear publisher는 구현되지 않았으므로
이 신호 없이 원격 이동은 의도적으로 불가능하다.

### 원격 제어 상태

| 토픽 | 타입 | 의미 |
|---|---|---|
| `/conveyor/state` | `std_msgs/msg/String` | 10 Hz JSON 상태 heartbeat |
| `/conveyor/moving` | `std_msgs/msg/Bool` | 명령 기준 이동 중 여부 |

상태 값은 `IDLE`, `MOVING_TO_ASSEMBLY`, `ASSEMBLY_STOP`,
`MOVING_TO_INSPECTION`, `INSPECTION_STOP`, `MANUAL_STOP`, `FAULT`다.
JSON에는 `schema_version`, `timestamp_ns`, `state`, `moving`,
`target_station`, `reason`, `armed`, `command_linear_x_mps`, vision/FR5
heartbeat 상태가 포함된다. 이는 모터 encoder feedback이 아니라 **제어 명령 상태**다.

기본 실제 벨트 전진 명령은 검증된 TurtleBot 매핑인
`TwistStamped.linear.x=-0.10 m/s`이고, 이동 시간 30초를 넘으면 `FAULT` 정지한다.

### 서비스별 허용 순서

- `move_to_assembly`: `IDLE` 또는 이전 `INSPECTION_STOP`에서만 허용
- `move_to_inspection`: `ASSEMBLY_STOP` 상태에서 허용
- 서버를 조립 정지 후 재시작한 경우에는 fresh assembly trigger가 `true`이면
  현재 조립 정지를 복구 근거로 인정하고 inspection 이동을 허용
- 선택한 목적지 trigger가 이미 `true`이면 재출발을 거부
- `FAULT` 또는 `MANUAL_STOP`에서는 `reset` 전까지 이동 거부

### `assembly-r1` 레시피 연동

팀 공통 레시피의 sequence operation은 다음처럼 매핑한다.

| 레시피 operation | ROS 연동 | 완료 조건 |
|---|---|---|
| `move_conveyor_to_assembly` | `/conveyor/move_to_assembly` 호출 | `/conveyor/state.state == "ASSEMBLY_STOP"` |
| `move_conveyor_to_inspection` | `/conveyor/move_to_inspection` 호출 | `/conveyor/state.state == "INSPECTION_STOP"` |
| 긴급/사용자 정지 | `/conveyor/stop` 호출 | `MANUAL_STOP`, `moving=false` |
| fault 복구 준비 | 원인 제거 후 `/conveyor/reset` 호출 | `IDLE`, `moving=false` |

서비스 `success=true`만 받고 다음 조립·검사 단계로 넘어가면 안 된다. 이는 이동
요청 수락을 뜻할 뿐이다. Main Server executor는 상태 heartbeat를 계속 감시하면서
목적지 STOP 상태를 받을 때까지 해당 recipe operation을 완료하지 않는다.

권장 흐름:

```text
before_all:
  FR5 clear heartbeat=true
  move_conveyor_to_assembly service accepted
  wait ASSEMBLY_STOP
  ensure_camera_calibrated

after_all:
  FR5 home/clear 확인 및 heartbeat=true
  move_conveyor_to_inspection service accepted
  wait INSPECTION_STOP
  inspect_assembled_pcb
  transfer_assembled_pcb
```

`assembly-r1` YAML을 파일로 전달할 때는 들여쓰기에 NBSP(U+00A0)가 아닌 일반
ASCII space를 사용해야 한다. 제공된 채팅 본문에는 NBSP가 섞여 있으므로 그대로
복사해 실행 파일로 사용하지 않는다.

## 5. DB 이벤트 저장 규칙

권장 이벤트 이름과 조건:

| DB 이벤트 | 생성 조건 | 저장 권장 필드 |
|---|---|---|
| `CONVEYOR_READY` | `stop_line_ready`가 `false -> true` | timestamp, ready, spacing_valid, board_count |
| `BOARD_SEEN` | station의 `board_detected`가 `false -> true` | timestamp, station, distance_px, polygon |
| `STATION_REACHED` | station의 `stop_trigger`가 `false -> true` | timestamp, station, distance_px, board_count |
| `CONVEYOR_VISION_FAULT` | ready=false 또는 heartbeat timeout | timestamp, last_ready_age_ms, spacing_valid |
| `BOARD_POSE` | 아래 position_valid=true | timestamp, station, base pose, status JSON |

- `stop_trigger=true`가 여러 프레임 반복되므로 **상승 에지만 한 번 저장**한다.
- DB 중복 방지를 위해 `(production_cycle_id, station, event_type)`에 unique key 또는
  idempotency key를 둔다.
- `stop_line_ready`와 station trigger가 250 ms 이상 갱신되지 않으면 마지막 `true`를
  신뢰하지 않고 통신 장애로 처리한다. 실제 모터 제어기는 더 엄격한 150 ms
  watchdog을 사용한다.
- ROS 메시지 header가 없는 Bool/Float32 토픽은 DB 수신 시각을 기록한다.

## 6. Unity 연결

ROS 컴퓨터에서 Endpoint를 실행한다.

```bash
cd ~/KSMC/Ros2UnityEndopoint_PKG_0.2/Ros2UnityEndopoint_PKG
./run.sh
```

- TCP listen: `0.0.0.0:10000`
- Unity ROS-TCP Connector의 ROS IP에는 Endpoint를 실행한 컴퓨터 IP를 입력한다.
- Unity 컴퓨터는 `ROS_DOMAIN_ID`를 직접 설정하는 대신 이 Endpoint를 통해 ROS 2와
  연결한다.

Unity C# 구독 예시:

```csharp
using RosMessageTypes.Std;
using Unity.Robotics.ROSTCPConnector;
using UnityEngine;

public class ConveyorRosView : MonoBehaviour
{
    bool previousAssemblyTrigger;

    void Start()
    {
        var ros = ROSConnection.GetOrCreateInstance();
        ros.Subscribe<BoolMsg>(
            "/vision/conveyor/stop_line_ready",
            msg => Debug.Log($"Conveyor vision ready: {msg.data}"));
        ros.Subscribe<Int32Msg>(
            "/vision/conveyor/board_count",
            msg => Debug.Log($"Board count: {msg.data}"));
        ros.Subscribe<BoolMsg>(
            "/vision/conveyor/assembly/stop_trigger",
            OnAssemblyTrigger);
    }

    void OnAssemblyTrigger(BoolMsg msg)
    {
        if (msg.data && !previousAssemblyTrigger)
            Debug.Log("ASSEMBLY station reached");
        previousAssemblyTrigger = msg.data;
    }
}
```

Unity에서 조립 위치 이동 서비스를 호출하는 예시:

```csharp
using RosMessageTypes.StdSrvs;
using Unity.Robotics.ROSTCPConnector;

ROSConnection.GetOrCreateInstance().SendServiceMessage<TriggerRequest,
    TriggerResponse>(
        "/conveyor/move_to_assembly",
        new TriggerRequest(),
        response => UnityEngine.Debug.Log(
            $"accepted={response.success}, message={response.message}"));
```

Unity 표시 상태 권장 매핑:

- `stop_line_ready=false` 또는 heartbeat timeout: `FAULT`/회색
- `board_detected=true`, `distance_to_stop_px > 20`: `APPROACHING`
- `stop_trigger` 상승 에지: `ASSEMBLY_STOP` 또는 `INSPECTION_STOP`
- `board_count >= 2`이고 `station_spacing_valid=true`: 두 기판 동시 표시 가능

## 7. 선택 사항: FR5 Base 기준 기판 pose

정지선 노드와 별도로 localizer를 실행해야 한다.

```bash
~/KSMC/run_s22_board_localizer.sh
```

| 토픽 | 타입 | 의미 |
|---|---|---|
| `/vision/board/{station}_pose` | `geometry_msgs/msg/PoseStamped` | FR5 `base` frame 기준 기판 중심 위치(m)와 장축 yaw |
| `/vision/board/{station}_position_valid` | `std_msgs/msg/Bool` | 위치와 크기가 캘리브레이션 유효 범위인지 여부 |
| `/vision/board/{station}_heading_valid` | `std_msgs/msg/Bool` | 현재 항상 `false`; 손잡이 방향을 포함한 0/180도 구분 미검증 |
| `/vision/board/{station}_status` | `std_msgs/msg/String` | 중심 mm, yaw, 크기 오차 등이 들어 있는 JSON 문자열 |

`PoseStamped`의 yaw는 현재 장축 기준 modulo 180°이므로 Unity에서 기판 방향을
확정하거나 로봇 명령에 사용하면 안 된다. `position_valid=true`인 중심 위치만
검증 후보로 사용한다.

## 8. 운영 실행과 안전 경계

비전/정지선 서버:

```bash
~/KSMC/run_s22_conveyor_hq.sh
```

수동 운전 시에는 원격 서버를 종료한 상태에서 장비 담당자만 아래 스크립트로
한 단계씩 실행한다.

```bash
~/KSMC/run_conveyor_to_assembly.sh
# FR5 조립 완료와 작업영역 이탈 확인 후
~/KSMC/run_conveyor_to_inspection.sh
```

자동 운전 시에는 수동 스크립트를 사용하지 않고 원격 서버와 위 서비스를 사용한다.
`release`와 생산 cycle ID 관리는 아직 Main Server 측 구현이 필요하다.

## 9. 빠른 확인 명령

```bash
ros2 topic echo /vision/conveyor/assembly/stop_trigger
ros2 topic echo /vision/conveyor/inspection/stop_trigger
ros2 topic echo /vision/conveyor/assembly/distance_to_stop_px
ros2 topic echo /vision/conveyor/inspection/distance_to_stop_px
ros2 topic echo /vision/conveyor/board_count
ros2 topic hz /vision/conveyor/stop_line_ready
ros2 topic echo /conveyor/state
ros2 service list | grep /conveyor
ros2 topic info /cmd_vel -v
```

`/cmd_vel` publisher가 둘 이상이면 실제 이동 전에 중복 제어 노드를 종료한다.

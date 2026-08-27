# ROS2 연동 API 명세

## 1. 개요

이 문서는 Unity 애플리케이션과 ROS2 노드 사이의 통신 인터페이스를 정의한다.
기준 씬은 `Assets/Scenes/SampleScene.unity`이며, 기본 활성 구성은 **Mock**이다.
Real 구성은 기본적으로 비활성 상태다.

Unity는 ROS-TCP Endpoint 노드(`/UnityEndpoint`)를 통해 ROS2와 통신한다.

`4.3`의 자동 조립 인터페이스가 현재 Mock MVP의 실행 계약이다. 전체 실행 경계는
[Architecture.md](../UnityDT/Docs/Architecture.md), HTTP 진입점은 [MainServer API](../MAIN_SERVER/Main_serverAPI.md)를 따른다.

## 2. 빠른 참조

| 기능 | Mock 인터페이스 | Real 인터페이스 |
| --- | --- | --- |
| 자동 조립 | `/unity/assembly/start` 서비스 + `/unity/assembly/feedback` 토픽 | 설계됨(미구현): `/real/assembly/start`·`status` 서비스 + `/real/assembly/progress` 토픽 |
| 수동 관절 목표 전송 | `/unity/joint_target` 토픽 | 미지원 |
| MoveJ 목표 전송 | `/unity/movej_target` 토픽 | `/fairino_remote_command_service` 서비스 |
| TCP 직선 이동 | `/unity/tcp_target` 토픽 | `/fairino_remote_command_service` 서비스 |
| 그리퍼 제어 | `/unity/gripper_target` 토픽 | `/fairino_remote_command_service` 서비스 |
| 로봇 상태 수신 | `/joint_states` 토픽 | `/nonrt_state_data` 토픽 |
| 명령 결과 확인 | `/twin_visual/status` 토픽 | 자동: `/real/assembly/progress`, 개별 이동: 서비스 응답 + `/nonrt_state_data` 완료 상태 |
| 비전 결과 수신 | `/vision/board/*` 토픽 | `/vision/board/*` 토픽 |

> Real의 공통 `IRobotControl.MoveJ`는 `RealRobotControl`이 `/fairino_remote_command_service`로
> 요청하고 `/nonrt_state_data`의 실제 완료 상태까지 기다린다. Scene의 세 티칭 포인트를
> 배정해야 사용할 수 있으며, 수동 관절 직접 제어는 아직 지원하지 않는다.

## 3. 공통 인터페이스

Mock과 Real이 동일하게 구독하는 비전 인터페이스다.

| 방향 | 이름 | 메시지 타입 | 용도 | 발행 노드 |
| --- | --- | --- | --- | --- |
| ROS2 → Unity | `/vision/board/image/compressed` | `sensor_msgs/CompressedImage` | HUD 카메라 영상 표시 | 비전 노드 |
| ROS2 → Unity | `/vision/board/capture/target_pose` | `geometry_msgs/PoseStamped` | 검출 대상 Pose 수신 (`base` 프레임) | 비전 노드 |
| ROS2 → Unity | `/vision/board/selected_target` | `std_msgs/String` | 선택된 검출 대상 ID 수신 | 비전 노드 |

## 4. Mock 인터페이스

### 4.1 Unity → ROS2

| 이름 | 메시지 타입 | 용도 | 수신 노드 |
| --- | --- | --- | --- |
| `/unity/joint_target` | `sensor_msgs/JointState` | 수동 관절 목표 적용 | `mock_movej` |
| `/unity/movej_target` | `geometry_msgs/PoseStamped` | MoveJ 목표 이동 | `mock_movej` |
| `/unity/tcp_target` | `geometry_msgs/PoseStamped` | TCP 직선 이동 | `mock_movej` |
| `/unity/gripper_target` | `std_msgs/Float32` | 그리퍼 열림 비율 변경 | `mock_movej` |

### 4.2 ROS2 → Unity

| 이름 | 메시지 타입 | 용도 | 발행 노드 |
| --- | --- | --- | --- |
| `/joint_states` | `sensor_msgs/JointState` | J1~J6 및 그리퍼 상태 동기화 | MoveIt/`joint_state_broadcaster` |
| `/twin_visual/status` | `std_msgs/String` | Mock 명령 완료·오류 확인 | `mock_movej` |

### 4.3 자동 조립 Mock MVP

신규 ROS 메시지를 만들지 않고 기존 타입을 재사용한다.

| 방향 | 이름 | 타입 | 용도 |
| --- | --- | --- | --- |
| Unity → ROS2 | `/unity/assembly/start` | `fairino_msgs/srv/RemoteCmdInterface` | 고정 레시피 1회 실행 요청 |
| ROS2 → Unity | `/unity/assembly/feedback` | `std_msgs/String` | 실행 단계와 최종 결과 callback |

MVP는 고정 레시피, 수량 1개, 동시 작업 1건만 허용한다. 실행 중인 작업이 있으면 새 요청을
거부한다. ROS 메모리 스냅샷으로 Unity 재접속 시 시각화 진행 상태를 복구하지만 작업 큐와
취소는 제공하지 않는다. `mock_sim.py` 직접 실행에는 DB 기록이 없고, `mock_db_bridge`를 사용하면
같은 외부 계약을 유지하면서 Job·Unit·재고·검사 결과를 `production`에 기록한다.

#### 시작 요청과 응답

`RemoteCmdInterface.cmd_str`에는 다음 JSON을 전달한다. `request_id`는 Guid 문자열이다.

```json
{
  "command":"start",
  "request_id":"7fba6ca7-461d-4f08-88ad-5412cfbfffe7",
  "recipe_version":"mock-r1",
  "observations":[
    {
      "order":1,
      "part_id":"HBM",
      "source":{"xyz_mm":[320.0,-110.0,95.0],"xyzw":[0.0,0.0,0.0,1.0]},
      "target":{"xyz_mm":[510.0,25.0,120.0],"xyzw":[0.0,0.0,0.0,1.0]}
    }
  ]
}
```

YAML은 `order`, `part_id`, `slot_code`, `joint_points`, `motion`을 결정한다. Unity는 기존
좌표변환을 사용해 각 부품과 슬롯 Transform을 `base_link` 기준 `wrist3` runtime pose로
변환하고 `observations`에 담는다. Unity는 `slot_code`를 보내거나 YAML 스텝을 수정하지 않는다.

ROS는 실행 전에 observation 개수와 각 `order`, `part_id`가 YAML과 일치하는지 확인한다.
검증을 통과하면 관측 Pose로 MoveIt 목표를 만들되 로드한 YAML은 변경하지 않는다.

`RemoteCmdInterface.cmd_res`는 다음 JSON이다.

```json
{"accepted":true,"request_id":"7fba6ca7-461d-4f08-88ad-5412cfbfffe7","error_code":"","message":""}
```

`accepted`는 요청 형식과 실행 가능 조건을 확인해 작업을 **수락했다**는 뜻이다. 조립 완료를
뜻하지 않는다. `accepted=false`이면 작업은 시작되지 않으며 `error_code`와 `message`에
원인을 담는다.

#### 재접속 상태 조회

Unity가 활성화되면 같은 서비스에 `{"command":"status"}`를 보내 마지막 ROS 메모리
스냅샷을 조회한다.

```json
{
  "available":true,
  "active":true,
  "request_id":"7fba6ca7-461d-4f08-88ad-5412cfbfffe7",
  "recipe_version":"mock-r1",
  "state":"PICKED",
  "placed_count":3,
  "expected_step_count":25,
  "held_step_order":4,
  "held_part_id":"Samsung970Evo",
  "held_slot_code":"SAMSUNG970EVO-01",
  "error_code":"",
  "message":""
}
```

Unity는 `placed_count`까지 기존 부품/슬롯 순서로 재배치하고
`held_step_order`가 있으면 해당 부품을 Mock 그리퍼에 다시 부착한 뒤 새 callback을 계속
반영한다. 이 스냅샷은 ROS 노드 재시작 시 사라지며, 현재 DB 기록도 실행 중 작업의 자동 재개를
제공하지 않는다.

#### feedback 형식

`std_msgs/String.data`에는 모든 상태가 동일한 JSON 필드를 사용한다.

```json
{
  "request_id":"7fba6ca7-461d-4f08-88ad-5412cfbfffe7",
  "state":"PICKED",
  "step_order":1,
  "part_id":"HBM",
  "slot_code":"HBM-01",
  "error_code":"",
  "message":""
}
```

| 필드 | 규칙 |
| --- | --- |
| `request_id` | 시작 요청의 Guid와 같아야 한다 |
| `state` | `STARTED`, `PICKED`, `PLACED`, `COMPLETED`, `FAILED` 중 하나 |
| `step_order` | 레시피 스텝 번호. 스텝과 무관하면 `0` |
| `part_id` · `slot_code` | 해당 스텝의 안정적인 식별자. 무관하면 빈 문자열 |
| `error_code` · `message` | `FAILED`에서 실패 원인. 그 외에는 빈 문자열 |

`PICKED`는 파지가 실제로 끝난 뒤, `PLACED`는 해제가 실제로 끝난 뒤 발행한다. Mock 구현은
각 callback에서 가상 부품의 attach/detach를 처리한다. `COMPLETED`와 `FAILED`는 terminal
상태이며 작업당 하나만 발행한다.

`MockAssemblyScenarioControl.ExecuteAsync()`는 `COMPLETED`를 받은 뒤에만 성공으로 끝난다.
`FAILED` 또는 terminal callback 타임아웃은 호출자에게 실패로 전달한다.

## 5. Real 인터페이스

### 5.1 Unity → ROS2

| 이름 | 서비스 타입 | 용도 | 수신 노드 |
| --- | --- | --- | --- |
| `/fairino_remote_command_service` | `fairino_msgs/srv/RemoteCmdInterface` | 이동·그리퍼 명령 요청 | `fr_command_server` |

### 5.2 ROS2 → Unity

| 이름 | 메시지 타입 | 용도 | 발행 노드 |
| --- | --- | --- | --- |
| `/nonrt_state_data` | `fairino_msgs/msg/RobotNonrtState` | 실기 로봇 비실시간 상태 수신 | `fr_command_server` |

### 5.3 자동 조립 Real (설계됨, 미구현)

#### API 목록

| 송신자 | 수신자 | 구분 | 이름 | 메시지 타입 | 목적 |
| --- | --- | --- | --- | --- | --- |
| Unity `RealAssemblyScenarioControl` | AIO `real_assembly` | 서비스 | `/real/assembly/start` | `real_assembly_interfaces/srv/StartAssembly` | Real 조립 시작 요청과 수락 결과 |
| Unity `RealAssemblyScenarioControl` | AIO `real_assembly` | 서비스 | `/real/assembly/status` | `real_assembly_interfaces/srv/GetAssemblyStatus` | 현재 또는 지정 조립 작업 상태 조회 |
| AIO `real_assembly` | Unity `RealAssemblyScenarioControl` | 토픽 | `/real/assembly/progress` | `real_assembly_interfaces/msg/AssemblyProgress` | 조립 진행과 최종 결과 전달 |

#### 메시지 구성

```text
# StartAssembly.srv
string request_id
string recipe_version
---
bool accepted
string request_id
uint32 expected_step_count
string error_code
string message
```

```text
# GetAssemblyStatus.srv
string request_id  # 빈 문자열이면 현재 또는 마지막 작업
---
bool available
bool active
string request_id
string recipe_version
string state
uint32 step_order
uint32 expected_step_count
uint32 placed_count
string part_id
string slot_code
string error_code
string message
```

```text
# AssemblyProgress.msg
string request_id
string recipe_version
string state
uint32 step_order
uint32 expected_step_count
uint32 placed_count
string part_id
string slot_code
string error_code
string message
```

| 필드 | 허용 값 |
| --- | --- |
| `state` | `STARTED`, `PICKED`, `PLACED`, `COMPLETED`, `FAILED` |
| `error_code` | `BUSY`, `INVALID_REQUEST`, `VISION_FAILED`, `COMMAND_FAILED`, `ROBOT_FAULT`, `TIMEOUT`, `INTERNAL_ERROR` |

## 6. Unity ROS-TCP Connector API

구현에서 사용하는 ROS-TCP Connector 호출은 다음과 같다.

| 방향 | Unity API | 역할 |
| --- | --- | --- |
| 송신 | `RegisterPublisher<T>(topic)` | 송신 토픽 등록 |
| 송신 | `Publish(topic, message)` | 토픽 메시지 발행 |
| 송신 | `RegisterRosService<TRequest, TResponse>(service)` | 서비스 클라이언트 등록 |
| 송신 | `SendServiceMessage<TResponse>(service, request)` | 서비스 요청 전송 및 응답 대기 |
| 수신 | `Subscribe<T>(topic, callback)` | 토픽 구독 시작 |
| 수신 | `Unsubscribe(topic)` | 토픽 구독 해제 |

## 7. 실행 상태 확인

ROS2 환경에서 실제 노드, 토픽, 서비스 상태를 확인한다.

```bash
ros2 node list
ros2 topic list
ros2 service list
```

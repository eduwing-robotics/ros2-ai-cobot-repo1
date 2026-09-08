# 하드웨어 비활성 상태의 Home Ghost 통신 테스트

`enable_hardware_execution=false`를 유지한다. 별도 활성화 파라미터는 필요 없다. 실제 명령 `/real/robot/command`는 계속 SAFETY_STOP으로 차단된다. 미리보기 요청은 **`/real/ghost/command`**로 보낸다.

## 토픽

| 용도 | 토픽 | 타입 |
|---|---|---|
| 미리보기 요청 | `/real/ghost/command` | `std_msgs/String` JSON |
| 미리보기 결과 | `/real/ghost/event` | `std_msgs/String` JSON |
| Ghost 관절 목표 | `/real/ghost/target` | `sensor_msgs/JointState`, rad |
| Ghost 단계 목표 | `/real/ghost/stage_target` | `std_msgs/String` JSON, deg/rad |

요청 전에 결과와 Ghost 토픽 구독을 연결한다. Ghost는 volatile이므로 구독 전에 보낸 목표는 재전송되지 않는다. 새 테스트마다 새 operation_id를 사용한다.

```json
{
  "job_id": "f97f2777-cbd7-4872-896e-24f09cc5ffe8",
  "operation_id": "6cbcbbd7-9ee5-4881-ab24-95ec0beb61d8",
  "action": "robot.move_joint",
  "point_name": "home",
  "joint_point": [-4.689, -86.951, 84.467, -87.516, -90.0, -4.688]
}
```

JSON은 기존 Home 요청과 같다. 바뀌는 것은 **발행 토픽**이다. Unity 예시:

```csharp
var ros = ROSConnection.GetOrCreateInstance();
ros.RegisterPublisher<StringMsg>("/real/ghost/command");
ros.Subscribe<StringMsg>("/real/ghost/event", msg => Debug.Log(msg.data));
// 구독 연결이 완료된 뒤 버튼에서 실행. operation_id는 Guid.NewGuid().ToString().
ros.Publish("/real/ghost/command", new StringMsg(homeRequestJson));
```

기존 `RealGhostStageReceiver` 또는 JointState 수신기는 그대로 사용할 수 있다. 같은 Ghost 관절을 두 수신기가 동시에 제어하지 않도록 프로젝트에 맞는 하나를 사용한다.

성공 응답 스키마는 `fr5.ghost_preview_event/v1`, `event=PREVIEW_PUBLISHED`, `preview_only=true`, `robot_motion_authorized=false`다. 동일 job_id/operation_id/action을 포함한다. 단계 메시지에도 `preview_only=true`가 추가된다. 발행 성공은 구독자 수신 확인이나 실제 로봇 이동 완료를 뜻하지 않는다. 실제 Sequencer의 OPERATION_COMPLETED 처리로 연결하면 안 된다.

실패 시 `event=PREVIEW_FAILED`, `error_code/message`를 확인한다. 관절 제한 조회를 위해 FR5 명령 서비스가 필요하다. 호출은 `GetJointSoftLimitDeg(1)`뿐이며 MoveJ/MoveL/MoveGripper/StopMotion/Reset 등의 명령은 보내지 않는다. Home처럼 관절값이 이미 제공된 요청에는 IK를 다시 계산하지 않는다.

현재 지원 범위는 **robot.move_joint 관절 목표 미리보기**다. pick/place/transfer 전체 단계 미리보기는 이 경로에서 지원하지 않으며 요청을 거부한다. 실제 경로 도달성·충돌·속도·그리퍼 동작 검증을 대신하지 않는다.

같은 operation_id/내용을 재요청하면 최근 128건 내 성공 결과를 재사용하고 Ghost는 다시 발행하지 않는다. 다른 내용으로 같은 ID를 쓰면 INVALID_REQUEST다. 새 목표 재발행에는 새 UUID가 필요하다.

상태 조회:

```bash
ros2 param get /real_robot_api enable_hardware_execution
ros2 service call /real/robot/status std_srvs/srv/Trigger '{}'
```

status는 hardware_execution_enabled=false와 ghost_preview_enabled=true, 지원 액션 및 요청·결과 토픽을 반환한다. 로봇 PC의 기본 실행은 `./run_fr5_assembly_stack.sh api-start`이며 하드웨어 비활성 설정을 유지한다.

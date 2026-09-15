# Unity Real 그리퍼·Ghost 연동 전달서

작성 기준일: 2026-09-04

## 실제 그리퍼 상태

- 토픽: `/nonrt_state_data`
- 타입: `fairino_msgs/msg/RobotNonrtState`
- `gripper_feedback_valid == true`일 때만 `gripper_position`을 반영한다.
- `gripper_position`은 0~100 범위이며 0은 닫힘, 100은 열림이다.
- 약 100Hz 상태 스트림을 사용하고 반복 서비스 조회는 하지 않는다.

## Real Ghost 목표

- 토픽: `/real/ghost/target`
- 타입: `sensor_msgs/msg/JointState`
- `name`: `[j1, j2, j3, j4, j5, j6]`
- `position`: J1~J6 최종 목표, rad 단위
- QoS: Reliable, Volatile, Depth 1

이전 2026-09-03의 `geometry_msgs/msg/PoseStamped` 계약은 폐기됐다. Unity는 같은
토픽에 두 메시지 타입을 동시에 남기면 안 되며 JointState 구독으로 교체해야 한다.

적용 규칙:

1. 관절 이동은 YAML에서 전달된 J1~J6 목표가 발행된다.
2. Cartesian 이동은 Real Backend가 `GetInverseKinRef`로 계산한 J1~J6가 발행된다.
3. Pick/Place/Transfer의 각 접근·하강·후퇴 arm 구간마다 최종 목표가 한 번 발행된다.
4. 그리퍼만 움직일 때는 Ghost 메시지가 없다.
5. 이동 중 실제 관절은 기존 `/nonrt_state_data`를 사용한다.
6. Ghost는 시각화 전용이며 수신 여부를 로봇 완료나 생산 흐름에 연결하지 않는다.

## 작업 API 이벤트

- 명령: `/real/robot/command`, `std_msgs/msg/String` JSON
- 이벤트: `/real/robot/event`, `std_msgs/msg/String` JSON
- Pause: `/real/robot/pause`, `std_msgs/msg/Bool`

Unity/Sequencer는 Pick/Place/Transfer에 XYZ나 회전값을 보내지 않는다. callback의
`OPERATION_COMPLETED`를 받은 후에만 다음 operation을 보낸다. 단, 현재 완료는
컨트롤러 동작 완료이며 실제 부품 파지·안착 성공 센서가 아직 없다는 점을 UI와
공정 판정에서 구분해야 한다.


## 단계 식별 Ghost 확장 — 2026-09-07

`/real/ghost/stage_target` String JSON과 `Assets/Scripts/RealGhostStageReceiver.cs`를
추가했다. operation_id/phase/target_id와 동일한 목표 관절을 한 메시지에 담는다.
기존 `/real/ghost/target` JointState 계약은 유지한다. 자세한 연결·축 설정과
검증 범위는 [Sequencer API 전달서](../docs/SEQUENCER_ROBOT_API_KO.md)를 참고한다.

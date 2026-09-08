> 2026-09-08 최신: [검증된 전체 사이클 API와 YAML 검토](ASSEMBLY_CYCLE_API_KO.md)를 참조하세요. 아래 개별 Pick/Place API와 전체 사이클 API는 실행 범위가 다릅니다. 과거 hardware=false 설명은 당시 기록이며 현재 활성화 상태는 상태 API로 확인합니다.

# Real 로봇 API 구현 계약

## 공개 토픽

| 용도 | 토픽 | 타입 |
|---|---|---|
| 작업 입력 | `/real/robot/command` | `std_msgs/msg/String` JSON |
| 이벤트 callback | `/real/robot/event` | `std_msgs/msg/String` JSON |
| 일시정지 요청 | `/real/robot/pause` | `std_msgs/msg/Bool` |
| Ghost 목표 | `/real/ghost/target` | `sensor_msgs/msg/JointState` |
| Backend 내부 비전 목표 | `/real/vision/targets` | `std_msgs/msg/String` JSON |

입력·callback 토픽은 최초 요구서에 이름이 없어서 위 이름을 기본값으로 정했다.
ROS parameter로 변경할 수 있다. 명령 JSON은 요구서의 필드를 그대로 사용하며,
Pick/Place/Transfer에 XYZ·회전 필드가 추가되면 `INVALID_REQUEST`로 거절한다.

## 구현된 처리 순서

1. UUID, action별 필수 필드, 개도율, 접근·후퇴 거리와 Backend 안전 상한 검사
2. Real 모드, Tool1/User0, 정지 상태, fault 및 E-STOP 검사
3. Backend 내부 Vision에서 최신 `base_link` TCP 목표 선택
4. 해당 operation의 모든 Cartesian 목표에 `GetInverseKinRef` 수행
5. 소프트 리밋 여유 10도, 관절 단계 95도, J6 운용 범위 ±178도 검사
6. 각 팔 이동 직전 J1~J6 최종 목표를 Ghost로 발행
7. `JNTPoint`와 `MoveJ`/`MoveL` 또는 `MoveGripper` 실행
8. `/nonrt_state_data`의 완료·목표 도달·fault·안전·timeout 확인
9. phase와 operation 완료/실패 이벤트 발행

Cartesian operation은 뒤쪽 한 구간이라도 IK가 실패하면 첫 이동 전에 전부
차단한다. 완료된 `operation_id`가 다시 들어와도 로봇 동작을 반복하지 않는다.

## 요구서 검토에서 확인된 미정 사항

### 물리 성공 판정

`robot_motion_done`과 `grip_motion_done`은 로봇 및 그리퍼 명령 완료만 뜻한다.
오늘 발생한 PM 미파지, VRM/IND/CAP 눌림, 슬롯 밖 배치를 판정하지 못한다.
따라서 현재 구현의 `OPERATION_COMPLETED`는 아직 물리 조립 성공을 뜻하지 않는다.
생산 사용 전 post-grasp 및 post-place Vision 또는 별도 센서가 필요하다.

### 교정값 소유권

Backend가 YAML/DB를 전혀 읽지 않으면서 정밀 파지하려면 Hand-Eye, TCP, 부품별
파지 보정, 슬롯 형상과 배치 보정을 누가 제공하는지 정해야 한다. 현재 구현은
이 값들을 Sequencer에서 받지 않고 Backend 소유 Vision 구성요소가 계산한 최종
내부 TCP 목표만 `/real/vision/targets`로 받는다. 기존 coarse Vision 출력은 오늘
실패한 정밀도이므로 직접 연결하지 않았다.

### Pause/Resume

`PAUSED` 이벤트와 Pause 요청은 구현했지만 최초 요구서에 resume/cancel 명령,
중단 지점 재개 규칙과 보유 부품 처리 규칙이 없다. 해당 계약 확정이 필요하다.

### 완성 PCB 이송

공개 명령에는 drop 위치 식별자가 없다. 현재 Backend 내부 Vision 목표가
`object_id`에 대응하는 pickup과 drop TCP를 둘 다 제공하도록 정의했다.

## 안전 상태

노드는 기본적으로 `enable_hardware_execution=false`이며 이때 모든 유효 명령은
`SAFETY_STOP`으로 끝나고 실제 FR5 명령은 전송되지 않는다. 활성화 여부와 별개로 최신 상태·Tool1/User0·fault·비전 목표·IK·경로 검사를 통과해야 동작한다.


## Sequencer 함수 API 확장 — 2026-09-07

함수 호출, 사용자 YAML 순서, source_index/파지 전 열림값, 단계별 Ghost 목표 및
정밀 비전 어댑터는 [Sequencer API 전달서](SEQUENCER_ROBOT_API_KO.md)를 참조한다.
기존 토픽과 legacy 입력 계약을 유지하며 하드웨어 실행 기본값은 false다.


하드웨어 비활성 상태의 Home Ghost 테스트는 [Ghost 전용 API 안내](REAL_GHOST_PREVIEW_API_KO.md)를 참고한다. `/real/ghost/command` 요청과 `/real/ghost/event` 결과는 실제 실행 경로와 별도다.


## 로봇 PC 하드웨어 실행 활성화 — 2026-09-08

사용자 요청에 따라 이 PC의 `config/ksmc.env`에 `KSMC_REAL_HARDWARE_EXECUTION=true`를 저장했다. `scripts/run_real_robot_api.sh`와 통합 스택은 이 값을 ROS 시작 파라미터로 전달한다. 값이 없는 다른 PC 및 노드 직접 실행의 기본값은 false다. 다시 비활성화하려면 해당 값을 false로 바꾸고 로봇 API를 재시작한다.

이 파라미터는 시작 시 내부 RobotPort에 복사되므로 `ros2 param set`만으로 전환하지 않는다. 실제 적용 여부는 `/real/robot/status` (`std_srvs/srv/Trigger`)의 `hardware_execution_enabled`로 확인한다. `api-start`는 이미 실행 중인 노드를 재설정하지 않는다.

API 프로세스만 `FASTDDS_BUILTIN_TRANSPORTS=UDPv4`로 실행하여 검증된 SHM 333ms 연결 대기를 우회한다. `KSMC_REAL_API_TRANSPORT`로 명시 설정할 수 있다. 드라이버·카메라의 전송 설정은 그대로다. 활성화 자체는 이동 명령을 보내지 않으며 교시값·물리 경로 검증 완료를 뜻하지 않는다.

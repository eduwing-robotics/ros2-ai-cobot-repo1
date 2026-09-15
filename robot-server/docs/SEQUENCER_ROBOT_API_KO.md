> 2026-09-08 최신: [검증된 전체 사이클 API와 YAML 검토](ASSEMBLY_CYCLE_API_KO.md)를 참조하세요. 아래 개별 Pick/Place API와 전체 사이클 API는 실행 범위가 다릅니다. 과거 hardware=false 설명은 당시 기록이며 현재 활성화 상태는 상태 API로 확인합니다.

# AssemblySequencer 로봇 API

Sequencer가 YAML을 읽고 순서를 소유한다. Robot Backend는 한 operation씩 수행하고
완료/실패 이벤트를 반환한다. 이번 구현은 실제 로봇을 실행하거나 활성화하지 않는다.

## 파일과 책임

- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/sequencer_robot_client.py`:
  함수 호출, YAML 부품별 인덱스 계산, ROS 송수신, 비동기 완료, 순차 실행.
- 같은 폴더 `real_contract.py`: 입력 필드와 범위 검증.
- `real_backend.py`: Pick/Place/Transfer 단계, 전체 IK 사전검사, 단계별 실행.
- `real_ros_node.py`: FR5 상태/명령 어댑터와 내부 비전 목표 수신.
- `real_ghost.py`: 기존 JointState와 단계 ID가 포함된 Ghost 목표 발행.
- `real_vision_adapter.py`: 기존 `full_cycle_plan.build_plan`을 호출해 정밀 보정된
  목표를 내부 API 형식으로 변환. 하드웨어 명령 없음.
- `assembly_integration/config/sequencer_recipe.example.yaml`: 사용자 제공 순서와
  값을 보존한 통합 예제. 기존 `assembly_recipe.yaml`과 실기 레시피는 변경하지 않았다.
- `unity_integration/Assets/Scripts/RealGhostStageReceiver.cs`: Ghost 전용 수신기.

## 함수 인터페이스

```python
moveJoint(point_name, joints_deg=None, *, operation_id=None) -> Future
pickItem(part_type, slot_code, *, operation_id=None, **values) -> Future
placeItem(part_type, slot_code, *, operation_id=None, **values) -> Future
transferItem(object_id="assembled_pcb", *, operation_id=None, **values) -> Future
pause()
```

`job_id`는 client 생성 시 UUID로 지정한다. 각 명령은 새 `operation_id` UUID를
생성한다. YAML을 전달했다면 함수의 생략값은 해당 YAML에서 가져온다.
YAML 없이 호출할 때 Pick에는 `order`, `source_index`, `approach_dz_mm`,
`retract_dz_mm`, `pregrasp_opening_percent`, `grasp_opening_percent`,
`release_opening_percent`를 전달한다. Place에는 이 중 파지/진입 개도율이 없다.
Transfer에는 object_id, 접근/후퇴 및 drop 접근 거리, 진입/파지/해제 개도율을 전달한다.

`source_index`는 종류별 1부터 시작한다. 사용자 순서의 CAP-01은 `order=14`,
`source_index=1`이다. API가 Sequencer의 전체 순번을 비전의 물리 부품 번호로
사용하지 않는다. 부품·슬롯·job·source_index와 보유 부품 관계를 검사한다.

```python
import yaml
from uuid import uuid4
from fr5_process_sequences.sequencer_robot_client import RosSequencerRobotClient

# node는 호출자가 소유하는 rclpy Node. ROS executor는 별도 스레드에서 spin한다.
with open("assembly_integration/config/sequencer_recipe.example.yaml") as source:
    recipe = yaml.safe_load(source)
api = RosSequencerRobotClient(node, job_id=str(uuid4()), recipe=recipe)

# Sequencer 작업 스레드에서 한 단계씩 호출하는 예:
api.moveJoint("home").result(timeout=120)
api.moveJoint("item_ready").result(timeout=120)
api.pickItem("HBM", "HBM-01").result(timeout=120)
api.moveJoint("home").result(timeout=120)
api.moveJoint("assembly_ready").result(timeout=120)
api.placeItem("HBM", "HBM-01").result(timeout=120)
```

위 코드는 API 사용 예시이며 이번 작업에서 실행하지 않았다. 기존 Backend의
`enable_hardware_execution=false` 기본값을 유지한다.

`iterWorkflow()`는 명령을 보내지 않고 YAML 순서를 열거한다.
`runRecipe(external_handlers, timeout_sec=120)`는 Sequencer 작업 스레드용 선택적
실행 래퍼다. 기존 Sequencer가 순서를 제어하면 개별 함수만 사용하면 된다.

```python
# 각 handler는 성공할 때까지 동기적으로 기다리거나 Future를 반환해야 한다.
api.runRecipe({
    "conveyor.move_to": conveyor.move_to,
    "vision.resolve_targets": vision.resolve_targets,
    "inspection.run": inspection.run,
})
```

전달 순서: HBM8 → PM4 → GPU1 → CAP5 → IND2 → VRM5.
각 부품은 Home → ItemReady → Pick → Home → AssemblyReady → Place.
전후 Conveyor/Vision/Inspection 호출은 제공된 handler가 담당한다.

Mock은 같은 `SequencerRobotClient`에 Mock send/pause 함수를 연결하거나,
`RosSequencerRobotClient`의 command/event/pause 토픽을 Mock 서버 토픽으로 지정한다.
이 구현은 별도의 가상 로봇 서버를 새로 실행하지 않는다.

## 요청/응답 토픽

| 용도 | 토픽 | 형식 |
|---|---|---|
| 명령 | `/real/robot/command` | `std_msgs/String`, JSON |
| 진행·완료 | `/real/robot/event` | `std_msgs/String`, JSON |
| Pause | `/real/robot/pause` | `std_msgs/Bool` |
| 내부 보정 목표 | `/real/vision/targets` | `std_msgs/String`, JSON |
| 기존 Ghost 목표 | `/real/ghost/target` | `sensor_msgs/JointState`, rad |
| 단계 식별 Ghost 목표 | `/real/ghost/stage_target` | `std_msgs/String`, JSON |

```json
{
  "job_id": "11111111-1111-4111-8111-111111111111",
  "operation_id": "22222222-2222-4222-8222-222222222222",
  "action": "robot.pick",
  "order": 14,
  "part_id": "CAP",
  "slot_code": "CAP-01",
  "source_index": 1,
  "approach_dz_mm": 100,
  "retract_dz_mm": 100,
  "pregrasp_opening_percent": 18,
  "grasp_opening_percent": 12,
  "release_opening_percent": 17
}
```

호환성을 위해 기존 `source_index` 없는 요청도 종전 global-order 계약으로 받는다.
새 Sequencer는 source_index를 보내고 새 비전 어댑터의 job/source 매칭과 실기
그리퍼 레시피 검사를 사용해야 한다. Cartesian XYZ/ABC를 공개 요청에 추가하면 거부한다.

진행은 `PHASE_STARTED`, `PHASE_COMPLETED`, `PAUSED`,
최종 결과는 `OPERATION_COMPLETED` 또는 `OPERATION_FAILED`이다.

2026-09-08 중복 요청 처리: 진행 중인 `operation_id`와 내용이 같은 요청은 기존 실행 결과를 기다린다. 추가 물리 동작이나 `ROBOT_BUSY` 최종 실패를 발생시키지 않는다. 활성 또는 완료된 ID로 다른 내용 또는 잘못된 요청을 보내면 비종결 이벤트 `REQUEST_REJECTED`와 `INVALID_REQUEST`를 반환하며 원래 실행과 최종 결과를 유지한다. 완료 결과를 저장한 직후 아직 원래 콜백이 전달되지 않은 경우에도 적용한다. 클라이언트는 이를 원래 작업의 완료/실패로 처리하지 않아야 한다. 다른 ID의 동시 요청은 기존처럼 `OPERATION_FAILED/ROBOT_BUSY`로 거부한다. 완료한 동일 요청의 재전송에는 저장된 최종 결과를 반환한다.
Future는 최종 이벤트에서만 완료되고 실패는 `OperationFailed` 예외가 된다.
다른 job/operation/action 이벤트는 현재 Future를 완료하지 않는다.

Timeout은 물리 작업 취소를 뜻하지 않는다. 전송 예외도 전달 여부가 불명확할 수
있으므로 client는 같은 operation의 결과 확인 전 다음 명령/자동 재전송을 막는다.
중복 operation 결과 캐시는 현재 Backend 프로세스 메모리에만 유지된다.
재시작 이후의 exactly-once 실행이나 자동 복구는 보장하지 않는다.
Pause 후 후속 단계는 중단하며 resume/cancel API는 이번 계약에 포함하지 않는다.

## IK와 단계별 Ghost

Cartesian operation의 모든 접근/하강/후퇴 목표를 먼저 `GetInverseKinRef`로
검사한다. 각 실제 이동 직전 최신 상태·현재 관절을 다시 읽고 IK를 재검증한다.
계산 분기가 사전검사 목표에서 1도 이상 달라지면 재계획이 필요하므로 거부한다.
기존 soft-limit 여유/관절 단계/J6 검사를 유지한다.
Joint 이동은 전달받은 J1~J6를 검증하고 IK를 다시 풀지 않는다.

`stage_target`에는 schema `fr5.ghost_stage_target/v1`, job_id, operation_id,
`target_id=operation_id:phase`, phase, point_name, timestamp_ros_ns,
joint_names, positions_rad, positions_deg, visualization_only=true가 포함된다.
Ghost에 발행한 최종 J1~J6를 같은 이동 명령에 사용한다. 그리퍼만 움직이는 단계는
팔 Ghost 목표를 발행하지 않는다. 실제 움직임은 `/nonrt_state_data`로 표시한다.

Unity의 **Ghost 복제 모델**에 `RealGhostStageReceiver`를 붙이고 J1~J6
ArticulationBody를 순서대로 할당한다. 기존 Calibration 모델의 축 부호/영점에 맞게
jointSigns와 jointOffsetsDeg를 설정한다. 기존 Ghost 드라이브 작성 컴포넌트와
동시에 사용하지 않는다. 단계는 StageChanged 이벤트와 Phase 속성으로 표시한다.
스크립트는 ROS 명령을 발행하지 않는다. Ghost 이동은 목표 미리보기 보간이며
실제 로봇의 경로·시간을 재현하는 시뮬레이터가 아니다.

Ghost 발행은 실제 이동보다 먼저 호출되지만 네트워크/Unity 프레임 지연 때문에
화면이 먼저 갱신되는 것까지 보장하지 않는다. Ghost acknowledgement를 기다려
동작을 승인하는 기능은 없다. Unity Editor 컴파일/씬 연결은 이 환경에서 미검증이다.

## 정밀 비전 연결 및 현재 실기 적용 범위

`build_target_payload`는 호출자가 넘긴 새 snapshot, 활성 실기 recipe와 slot 설정으로
기존 정밀 플래너를 호출한다. 보정된 pick/place TCP를 사용하며 높이·XY·성공한
회전 방향·그리퍼 값의 별도 계산 사본을 만들지 않는다.

CLI `real_precision_targets --help`는 입력 파일과 출력 옵션을 안내한다.
`--publish`를 지정해야 내부 목표 토픽에 한 번 발행한다. 기본은 JSON 저장만 한다.
원래 측정 시각을 유지하고 기존 Real API 기본 freshness 2.5초를 완화하지 않는다.
따라서 순차 카메라 촬영으로 오래된 전체-cycle snapshot을 그대로 연결하면
거부될 수 있다. 실제 순차 운전에는 운영 중인 비전 생산자가 현재 유효한 목표를
공급해야 하며, 과거 snapshot의 시각을 갱신해서 통과시키면 안 된다.
어댑터 CLI는 비전/카메라를 자동 이동하거나 주기적으로 재촬영하지 않는다.

내부 목표에는 검증된 진입/파지/해제 개도율과 각 단계의 속도·힘을 포함한다.
SMD의 force=1을 유지하며 2인자 MoveGripper의 드라이버 기본 힘을 사용하지 않는다.
현재 v3.9.7 래퍼는 첫 네 인자(index,position,velocity,force)를 읽고
controller max_time=30000ms/block=1을 고정하므로, Backend가 피드백으로 완료를
별도 확인한다. 드라이버 소스는 이번에 변경하지 않았다.

제공 YAML은 Home/ItemReady/AssemblyReady가 같은 임시 교시이고 PM/CAP/IND/VRM
개도율이 현재 실기 값과 다르다. 예제의 값은 임의로 수정하지 않았다. 새 source_index
요청은 실제 보정 목표의 그리퍼 값과 일치하지 않으면 이동 전에 INVALID_REQUEST로
거부한다. SMD 진입18/파지12/해제17은 세 개의 다른 값이다.

현재 Real Backend의 단순 접근 경로는 기존 전체 조립 런처의 모든 중간 경유점,
파지 후 TrayHome 제거 검사까지 이식한 것이 아니다. 준비점 실기 교시, 해당 경로
검증, 신선한 비전 목표 공급 및 완성 PCB pickup/drop 교정이 실기 적용 전에 필요하다.
이번 전달물은 API/순서/Ghost 통합 구현이며 무인 실기 조립 성공을 뜻하지 않는다.

## 검증

```bash
source scripts/ksmc_env.sh
PYTHONPATH="$PWD/ros2_ws/src/fr5_process_sequences:$PYTHONPATH" \
  python3 -m pytest ros2_ws/src/fr5_process_sequences/test -q
```

Mock 전체25 흐름, 작업151개/외부단계4개, Ghost256개,
실제 정밀 플래너와 어댑터 연결, 부품 번호, 원래 관측 시각 보존,
그리퍼 불일치·IK실패·Pause 차단, 타임아웃 및 중복 명령을 검사한다.
실기 명령과 Unity Editor 실행은 시험에 포함하지 않는다.

## 로봇 PC 실제 연결 — 2026-09-07

`./run_fr5_assembly_stack.sh api-start`는 기존 드라이버·카메라·Endpoint를
재시작하지 않고 로봇 API만 추가한다. `scripts/run_real_robot_api.sh`는
hardware execution=false를 명시한다. 스택의 다음 전체 start에도 API가 포함된다.
`/real/robot/status` (`std_srvs/srv/Trigger`)는 캐시된 로봇 상태와 API 활성화
상태를 JSON으로 반환하며 로봇 명령을 호출하지 않는다.

현재 로봇 PC `192.168.11.5:10000`에 외부 Unity 클라이언트
`192.168.11.14`의 TCP 연결을 확인했다. API 상태 조회와 의도적으로 지원하지
않는 connection_check 요청의 INVALID_REQUEST 응답으로 명령/이벤트 왕복을
확인했다. 진단 중 이동·그리퍼 명령은 보내지 않았다.

기존 `/real/ghost/target` JointState는 Unity Endpoint 구독자와 연결됐다.
`/real/ghost/stage_target`의 발행자는 준비됐지만 외부 Unity 구독은 아직 없다.
외부 Sequencer의 `/real/robot/command` 발행자와 `/real/robot/event` 구독자,
내부 정밀 비전 목표 발행자도 아직 연결되지 않았다. 이 PC에 Sequencer/Unity
본체 프로젝트가 발견되지 않아 해당 PC/프로젝트 경로 확인이 필요하다.
실제 연결 점검 기록: `runtime/assembly_stack/api_connection_check.json`.


하드웨어 비활성 상태의 Home Ghost 테스트는 [Ghost 전용 API 안내](REAL_GHOST_PREVIEW_API_KO.md)를 참고한다. `/real/ghost/command` 요청과 `/real/ghost/event` 결과는 실제 실행 경로와 별도다.

# 단계 콜백·부착·정지/재개 요구서 적용 검토

기준: `/home/juchan-yoon/Downloads/GRIPPER_ATTACHMENT_REQUIREMENTS_KO.md`.
2026-09-08 현재 소스와 실행 기록을 비교한 변경안이다. 아래 제안은 구현·실기 완료 선언이 아니다.
현재 IND-01은 GRIPPER_FAILED로 실패 종료됐고 사용자가 파지 높이에서 보유를 확인했다. 일반 resume를 적용할 수 없다. 이 검토에서는 로봇·그리퍼 명령, 오류 초기화, API 재시작을 하지 않았다.

## 확인된 현재 구현

| 요구 | 확인 결과 | 변경 필요 |
|---|---|---|
| 단계 시작/완료 | PrecisionSteps가 이동 단계와 PREOPEN/GRASP/RELEASE 이벤트 발행 | 기존 이름 유지, 대상·피드백 정보 추가 |
| 부착 시점 | GRASP 완료는 그리퍼 검증 뒤 상승 전, RELEASE 완료는 검증 뒤 후퇴 전 | 해당 이벤트만 부착/해제에 사용 |
| 원본 source_id | 트레이 Unity 메시지는 `part_type:두자리 instance` ID를 생성하지만 snapshot→API 대상→이벤트에 원본 ID가 보존되지 않음 | 관측 생성 시 ID 부여 후 전달 전 경로 보존. 소비 측에서 이름을 추정하지 않음 |
| 등록/실행 매핑 | source_cycle_id와 plan_sha256 존재, 명시적 트레이 등록 세대와 Unity 기판 연결 없음 | 등록 ID·관측 ID·Unit UUID·표시 기판 연결 필요 |
| 객체 보호 | 제공 TrayVisionSynchronizer는 매 관측 위치를 덮어쓰고 누락 객체를 Destroy | 예약/보유/배치/미확인 객체를 관측 갱신·삭제·재생성에서 보호 |
| 전체 완료 대기 | Python client는 job/operation/action 일치와 OPERATION_COMPLETED/FAILED만 처리 | 유지. Unity 실제 Sequencer의 대기 등록·차단은 원본 확인 필요 |
| 정지 | Bool true → pause 요청, 새 피드백 정지 조회 후 PAUSED 이벤트. 정지 미확인도 PAUSED 유형으로 전달될 수 있음 | 제어 요청 ID, 확인/실패 구분 필요 |
| 실행 유지 | `_assert_not_paused()`가 예외를 발생시켜 OPERATION_FAILED와 복구 대기로 종료 | 유지 가능한 pause 상태머신을 별도 구현 |
| resume | Real API에 대응 제어 요청·결과·보존 문맥 없음. Bool false는 무시 | 실패 이력 초기화나 새 Pick으로 대체 금지 |
| 재접속 | 현재 API status는 활동·보유 후보·계획 해시 제공 | 이벤트 순번/서버 세대, 부착 근거, pause 상태와 재개 불가 사유 필요 |

근거 소스:
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_precision_steps.py`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_backend.py`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_ros_node.py`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_vision_adapter.py`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/sequencer_robot_client.py`
- `vision_assembly/scripts/detect_tray_parts.py`
- `unity_integration/Assets/Scripts/TrayVisionSynchronizer.cs`

## 그리퍼 상태와 이번 실패의 관계

현재 드라이버 v3.9.7의 robot_types.h는 완료 상태를 0=미완료, 1=완료/물체 감지, 2=완료/물체 미감지로 정의한다. ROS 드라이버는 이를 그대로 전달한다. 감지의 내부 전류/힘/개도 알고리즘은 이 정의만으로 확정할 수 없다.

요구서는 1초 연속 **완료 피드백** 뒤 콜백을 요구하며, 콜백을 실제 보유의 완전한 증거라고 하지 않는다. 따라서 `motion_completed`, `controller_object_detected`, `physical_holding_verified`를 분리해야 한다. 상태2 자체를 '동작 미완료'라고 부르면 안 된다.

직전 수정본은 개방/해제에서 1·2를 허용하지만 GRASP2는 별도 미감지 실패로 종료한다. 이것은 추가적인 현재 실행 정책이며, 요구서가 반드시 상태1만 허용하라고 명시한 것은 아니다. 반대로 문서도 상태2에서 확인 없이 자동 상승하라고 승인한 것은 아니다.

권장 처리: GRASP2의 지속이 확인되면 실제 파지 단계와 피드백을 표시하고, 부착 확정·상승을 차단한 확인 대기로 전환한다. 이를 재개 가능한 상태로 만들려면 아래 유지 문맥과 작업자 확인의 기록·식별·유효기간을 구현해야 한다. 현재 이미 실패한 IND01에 소급 적용하지 않는다. 검증 규칙을 단순 삭제하거나 원래 실패 이벤트를 성공으로 고치지 않는다.

## 제안하는 이벤트 계약

기존 `/real/robot/event`, String JSON 및 바깥 7개 필드 유지. 현재 phase 이름 PREOPEN/GRASP/RELEASE와 순번이 붙은 이동 단계 재사용.

message JSON의 추가 정보 제안:

```json
{
  "schema": "fr5.robot_event_context/v1",
  "source_id": "<관측 parts[].id 원본>",
  "tray_registration_id": "<등록 세대>",
  "source_observation_id": "<고정한 관측 식별자>",
  "source_cycle_id": "<현재 기존 cycle_id>",
  "part_id": "IND",
  "source_index": 1,
  "slot_code": "IND-01",
  "order": 19,
  "event_sequence": 123,
  "server_instance_id": "<API 기동 세대>",
  "reason": "<기존 원인 문자열 보존>",
  "feedback": {
    "state_sequence": 100901,
    "observed_unix": 1788862536.69,
    "motion_completed": true,
    "controller_object_detected": false,
    "physical_holding_verified": false
  }
}
```

이는 형식 예시이며 실제 성공 이벤트가 아니다. 정확한 source_id를 찾지 못하면 다른 부품으로 대체하지 않고 표시 부착 불가를 명시한다. 임의 생산 Job ID를 만들지 않는다. Pick→Place는 같은 원본 객체 연결을 유지하고 각 요청 operation_id는 구분한다. Backend 안에서 확정한 관측 바인딩을 사용하며 Unity의 표시 성공 여부는 로봇 실행 허가 조건으로 만들지 않는다.

## Unity 변경

- Pick 첫 유효 PHASE_STARTED 때 등록ID+source_id로 기존 Calibration 객체를 예약한다.
- 객체 관리 상태: observed → reserved → attached → placed. 오류/끊김 시 마지막 부모를 유지하면서 uncertain 표시를 별도로 켠다.
- GRASP PHASE_COMPLETED에서만 실제 그리퍼 Transform으로 `SetParent(target, true)`.
- RELEASE PHASE_COMPLETED에서만 연결된 기판 Transform으로 동일 처리. 슬롯 스냅·Ghost 부착 금지.
- 예약/보유/배치 객체는 Calibration 좌표 덮어쓰기, 누락 삭제, 수동 재생성과 중복 생성을 모두 차단한다.
- ROS 수신은 큐에 넣고 Unity Update에서 적용한다. 실행/등록/operation/action/phase/event를 대조하고 순번으로 중복·역행을 거부한다.
- 원본 객체나 기판 연결이 없으면 임의 생성하지 않고 표시 미확인 상태 유지.

현재 로컬에는 전달용 스크립트만 확인됐으며 실제 AssemblySequencer/Calibration/RealBackend Unity 원본을 찾지 못했다. 실제 원본 프로젝트 위치 확인이 필요하다. 전달용 TrayVisionSynchronizer만 고쳐 원본 Calibration까지 해결됐다고 주장하지 않는다.

## 정지와 재개의 구현 전제

1. Bool 정지 호환은 유지하되 제어 request ID를 갖는 요청/결과 계약 추가. 이벤트는 기존 robot/event 사용. Unity 요청은 요구서대로 기존 Sequencer 진입점을 통과한다. 신규 Real 제어 요청 경로/형식은 Unity 원본과 함께 확정한다.
2. 요청 즉시 다음 동작 차단. 실행 worker·현재 waypoint·그리퍼 처리 단계·계획 해시·보유 문맥·operation_id를 유지한다.
3. 실제 새 피드백 0.5초 정지 확인 전에는 PAUSED_CONFIRMED를 발행하지 않는다. timeout/거절은 별도 결과로 차단 유지.
4. 중단된 컨트롤러 이동을 실제로 유지·재개하는 API 의미를 확인한다. 현재 사용 중인 외부 MoveL/MoveJ에 대해 script resume만 호출하거나 같은 목표를 다시 보내는 것을 정상 resume로 간주하지 않는다.
5. 재개 전 실행 문맥, 보유/그리퍼 상태, 로봇 오류, 같은 계획, 실제 시각 기준 계획 유효기간 확인. 실패/재시작/보유불명/만료는 거절하고 별도 복구한다.
6. 확인된 pause 구간만 동작 timeout에서 제외한다. 비전 유효기간은 연장하지 않는다. 제어 timeout은 계속 흘러야 한다.
7. pause와 전체 완료 경합은 완료를 한 번만 기록하고 Sequencer 차단은 유지. resume 확인 후 첫 미실행 동작부터 진행.
8. 백엔드/Sequencer 재시작 후에는 자동 resume 불가. 상태 조회에 재개 불가 사유와 원래 실패/보유 근거를 노출한다.

## 구현·검증 순서

1. 원본 관측 ID/등록 세대/실행 매핑 보존과 이벤트 message 정보 추가. 기존 phase·전체 완료 구분 유지.
2. 실제 Unity 원본에서 객체 보호·메인스레드 부착·중복/재접속 처리 연결.
3. 가짜 로봇으로 유지 문맥 pause/resume 상태머신과 Sequencer 차단·경합 검증.
4. 컨트롤러 pause/resume 의미 확인 후 빈 그리퍼 상태에서 이동 pause/resume 실기 검증.
5. 통제된 한 부품 시험으로 파지·해제 중 정지, 실제 보유, 부착 타이밍 검증. 그 뒤 전체 사이클.

필수 자동 검증: 개방 상태2, 파지 상태1/2, 해제 상태2, 미완료0, 잘못된 상태/개도/오류, 중복·끊긴 피드백, 파지 완료 전 부착 없음, 해제 완료 전 부모 변경 없음, 실패 후 상승 없음, 제어 ID 불일치, 정지 확인 timeout, pause/완료 경합, 만료 중 resume, 서버 재시작·오래된 조회·중복 이벤트, 객체 누락·등록 변경·수동 재생성 차단.

현재 검토로 해결되지 않은 것: IND01 보유 복구, 그리퍼 물체 미감지의 장치 내부 원인, 실제 Unity 연결, 유지 문맥 resume의 실기 지원/검증. 실제 장비는 정지·보유 상태를 유지한다.

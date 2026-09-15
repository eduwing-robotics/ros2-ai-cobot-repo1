# Unity 담당자 전달용 — FR5 로봇 단계 API 통합 명세

문서 버전: **2026-09-09 / v1.5** · 대상: 현재 FR5_robot_control 로봇 Backend와 Unity/Sequencer 연동 담당자

이 파일 하나로 요청·이벤트·부착·상태 조회·취소·최신 속도·남은 연동 항목을 확인할 수 있다. 9월 8일 단계 API, 전체 런처 API 연결, 콜백/부착, 연속 이동 문서의 변경 상태를 통합한다. 과거 ZIP의 batch AssemblyCycleClient를 생산 실행 진입점으로 사용하지 않는다. 이 문서는 Unity 코드나 생산 YAML을 자동으로 변경하지 않는다.

## 1. 지금 사용할 실행 계약

**Sequencer는 로봇 동작을 한 개씩 요청하고, 같은 요청의 OPERATION_COMPLETED를 받은 뒤 다음 동작을 보낸다.** 로봇 Backend가 좌표 보정, IK, 안전 경유점, 그리퍼 피드백과 트레이 제거 검사를 담당한다.

| 동작 | Backend 동작 범위 | 정상 종료 지점 |
|---|---|---|
| `robot.move_joint` | 관절 목표 이동. `PlaceCamera`·`TrayHome`·`SMDView`는 Backend의 카메라 안전 경로로 실행 | 지정 카메라/관절 목표 |
| `robot.pick` | 요청한 부품 하나 접근 → 개방 → 하강 → 파지 → 상승 → TrayHome 이동 → 해당 셀 제거 검사 | TrayHome |
| `robot.place` | 완료한 Pick과 일치하는 부품 하나를 해당 슬롯에 배치 → 해제 → 수직 후퇴 | 슬롯 위 100mm |
| `robot.transfer` | 계약 파서는 존재하지만 현재 assembled PCB 이송은 미검증·거절 대상 | 생산 연동 제외 |

Pick 안에 TrayHome 이동과 제거 검사가 들어가는 것은 합의된 동작 범위다. 이를 YAML의 다음 Home/준비점 이동 완료로 간주하지 않는다. Pick/Place가 다음 부품을 자동 실행하지 않는다.

`/real/assembly/command`의 batch `assembly.start`는 현재 Real bridge에서 차단한다. 로컬 `run_fr5_cycle.sh --execute`도 촬영 이동과 각 Pick/Place를 `/real/robot/command`로 요청한다.

### 9월 9일 반영 상태

- 카메라 경로도 전체 배율40%, 높은 수평 이동·회전40, 긴 수직30, 출발/도착 근접50mm10 적용. 카메라 API의 높은 동일 높이 구간에 연속 이동 추가.
- 로봇 API 빌드·설치본 일치 확인 후 유휴·정지·보유없음·복구없음과 실행 잠금 확인하에 API만 재시작. `run_fr5_cycle.sh --check` 통과.
- 전체 오프라인 시험 **714개**, Python 구문179개 통과. 새 카메라 속도의 실제 왕복·취소 정지·시간 단축은 아직 미검증.
- 어제 IND 보유/실패는 현장 확인과 해제·복귀 후 기록을 보존하여 복구 완료했다. 9월 9일 검사 당시 active_operation=null, held_candidate=null, recovery_required=false였다. 시작할 때마다 새로 조회한다.
- 새 단계 API 실기는 9월 8일 GPU/HBM/PM/VRM 18개 배치 동작 후 IND-01 파지 피드백에서 중단된 기록이 있다. 최신 전체25개 성공이나 생산 품질 PASS로 해석하지 않는다.

### 10:24 첫 카메라 실기 중단 후 정착 확인 수정

실행 `20260909-102430-737123`은 첫 수직 상승을350mm 목표/349.577mm 관측으로 완료 판정한 뒤, 연속 이동의349.8mm 진입 기준에 미달하여 중단됐다. 일반 도착1mm 허용오차와 연속 진입 조건 사이에 정착 대기가 빠져 있었다. 이후 읽기 관측은349.999mm 정지였다. 카메라 수평 이동·파지·배치는 실행되지 않았다.

v1.1은 연속 그룹 전·점 정의 후에 최대2초간 서로 다른 새 피드백을 읽으며, 진입높이 `max(349.8, 계획높이−0.2)mm` 이상/정지0.2초 연속 확인을 추가했다. 기존 관절 참조1.5도·모드/프레임·건강·취소 검사는 유지한다. 미정착이면 새 Move 명령을 보내지 않는다. 실패 상태/기록을 자동 해제하거나 원래 작업을 재생하지 않는다. 711개 오프라인 시험 통과이며 수정 후 실기 재시험은 아직 없다. 이 중단 이후에는 아래 과거 유휴 검사 결과를 현재 실행 허가로 사용하지 말고 recovery_required와 정지 상태를 새로 조회한다.

사용자 명시적 복구 요청 후 정지 래치를 해제하고201개 새 정지 표본을 확인했다. 실패 이벤트는 보존하며 복구 차단과 이전 소유권을 해제했다. API 유휴/보유후보없음/건강상태 정상 확인. 수정 후 카메라 실기 재시험과 새 전체사이클은 아직 실행하지 않았다.

### 10:33 재시험 후 큐 검사 연결 수정

실행20260909-103305-802491에서 첫 연속 MoveJ 수락 직후, 카메라 경로의 반복 검사 callback이 정지까지 요구하여 ROBOT_BUSY로 중단됐다. v1.2에서는 이 callback을 취소 검사로 한정하고, 큐 전송 중에는 별도의 실제 포트 검사로 실기활성/최신상태/오류/AUTO/Tool1/User0를 확인한다. 일반 단독 이동의 정지 요구는 그대로다. 실제 포트 메서드를 사용해 이동 중 후속명령·오류·취소 모의시험을 추가했고714개 통과. API에 적용했으나 수정 후 실기 재시험은 아직 없다. 이 두 번째 실패도 후속 사용자 명시적 요청으로 복구했다. 원래 실패이벤트를 보존하면서 정지 래치/복구차단/소유권을 해제했고201개 새정지표본 및 API유휴·건강상태를 확인했다. 로봇 이동과 새사이클은 시작하지 않았다.

카메라가 TrayHome 위350mm에서 중단되면 기준 TrayHome337.880mm를 벗어나 at_trayhome=false가 되므로 섹션 오버레이는 숨겨진다. 통합 영상은 계속 수신되며 서비스 미기동을 의미하지 않는다. 기준 자세 복귀와 새 등록 확인 전에는 오버레이를 강제 활성화하지 않는다.

## 2. 연결과 메시지

로봇 PC의 ROS_DOMAIN_ID는 **5**, Unity ROS-TCP Endpoint는 **로봇 PC IP:10000**이다. `0.0.0.0`은 서버 바인드 주소이므로 Unity 접속 주소에 쓰지 않는다. 네트워크 연결 후 먼저 이벤트를 구독하고 상태를 조회한다.

| 경로 | ROS 타입 | 용도 |
|---|---|---|
| `/real/robot/command` | `std_msgs/msg/String` | `data`에 요청 JSON 문자열 |
| `/real/robot/event` | `std_msgs/msg/String` | `data`에 이벤트 JSON 문자열 |
| `/real/robot/status` | `std_srvs/srv/Trigger` | 빈 요청, `response.message`에 상태 JSON 문자열 |
| `/real/robot/pause` | `std_msgs/msg/Bool` | `data=true`: 현재 동작 취소/정지, 자동 재개 기능 아님 |
| `/real/robot/control` | `std_msgs/msg/String` | 상관 ID가 있는 retained pause/resume. 현재 기본 비활성 |
| `/real/assembly/robot_state` | `std_msgs/msg/String` | 실측 관절/TCP 표시용 호환 스트림 |
| `/real/ghost/target` | `sensor_msgs/msg/JointState` | Ghost 목표 관절, 라디안 |
| `/real/ghost/stage_target` | `std_msgs/msg/String` | Ghost 단계/작업 상관 정보 |
| `/real/ghost/command`, `/real/ghost/event` | `std_msgs/msg/String` | 미리보기 전용 요청/결과, 실기 실행 아님 |
| `/real/vision/targets` | `std_msgs/msg/String` | Backend 비전 준비 데이터. Unity 로봇 명령과 별개 |

robot 이벤트 publisher는 RELIABLE / VOLATILE / depth100이다. 재접속 구독만으로 과거 이벤트가 재생되지 않는다. 상태 조회와 동일 요청 재전송을 사용한다. Unity 객체 조작은 메인 스레드에서 처리한다.

## 3. ID와 좌표 소유권

- `job_id`: 물리 PCB 한 장의 **Unit 실행 UUID**. 생산 Job UUID를 여러 PCB에 그대로 재사용하지 않는다.
- `operation_id`: 그 Unit의 개별 로봇 동작 UUID. Pick과 Place는 서로 다른 ID다.
- `order`: 준비된 레시피 행 순서. 전송 횟수나 이벤트 순번이 아니다.
- `part_id`: GPU/HBM/PM/VRM/IND/CAP. CAP은 SMD(`right_white_brown`)와 같은 부품군이다.
- `slot_code`: HBM-01 등 배치 슬롯. `source_index`: 준비된 계획의 부품 종류별 1부터 시작하는 트레이 인덱스.
- `source_id`: 검출기가 부여한 원래 관측 객체 ID. `source_index`와 다르며 opaque 문자열이다. ID에서 순번을 파싱하지 않는다.

Unity는 TCP XYZ/회전 보정값, 파지 높이, 임의 속도를 로봇 요청에 넣지 않는다. 선언되지 않은 필드는 INVALID_REQUEST다. Backend가 새 관측·현재 슬롯/레시피·성공 방향으로 실제 목표를 만든다. `joint_point`만 J1~J6 **도 단위**이며 임의 TCP 배열이 아니다.

생산 매핑은 Backend 준비 스냅샷의 `execution_context`로 제공한다. `execution_job_id`는 job_id와 같아야 한다. `production_job_id`와 양의 정수 `unit_id`는 함께 제공하고 `display_board_id`는 선택이다. 이 필드들을 `/real/robot/command`에 추가하지 않는다. 제공하지 않은 생산 ID는 추측하지 않는다.

## 4. 요청 예시

아래 예시의 UUID는 설명용이다. 실제 장면 준비 없이 게시하지 않는다. `order`와 `source_index`는 해당 Unit의 prepared_execution과 일치해야 한다.

### HBM-01 Pick

```json
{
  "job_id": "f85aeace-5205-4788-ac7a-d202405e26c3",
  "operation_id": "b6e0fe31-072e-48d9-970a-1ffdf47104e4",
  "action": "robot.pick",
  "part_id": "HBM",
  "slot_code": "HBM-01",
  "order": 1,
  "source_index": 1,
  "approach_dz_mm": 100.0,
  "retract_dz_mm": 100.0,
  "pregrasp_opening_percent": 25,
  "grasp_opening_percent": 18,
  "release_opening_percent": 25
}
```

현재 precision 구현에서 source_index와 pregrasp 값은 Pick에 필요하다. 접근/후퇴는 각각100mm만 지원한다. 일반 파서의 최대 허용 범위를 실기 지원 범위로 해석하지 않는다.

### 같은 부품 Place

```json
{
  "job_id": "f85aeace-5205-4788-ac7a-d202405e26c3",
  "operation_id": "20c06784-4c33-46de-bb02-22f95e7a69f8",
  "action": "robot.place",
  "part_id": "HBM",
  "slot_code": "HBM-01",
  "order": 1,
  "source_index": 1,
  "approach_dz_mm": 100.0,
  "retract_dz_mm": 100.0,
  "release_opening_percent": 25
}
```

Place에는 pregrasp/grasp 필드를 보내지 않는다. 완료 Pick의 job/part/slot/order/source_index와 일치해야 한다.

### PlaceCamera 이동

```json
{
  "job_id": "f85aeace-5205-4788-ac7a-d202405e26c3",
  "operation_id": "46c1b6d3-8c47-42b8-bb74-3b482ec20623",
  "action": "robot.move_joint",
  "point_name": "PlaceCamera",
  "joint_point": [81.355003, -98.153999, 97.530998, -89.375, -90.0, -8.645]
}
```

위 관절값은 현재 저장된 PlaceCamera 티칭 참고값이다. 실제 요청은 현장 검토된 준비점과 맞춰야 하며 Backend가 현재 경로 끝 관절과 대조한다. 카메라 이름만 보내면 안 된다. SMDView 관절을 TCP에서 Unity가 임의 계산하지 않는다. 카메라 이동은 보유 후보가 있으면 거절하며, 완료 응답 자체가 촬영 완료는 아니다. 영상 수집은 별도 비전 단계다.

### 현재 그리퍼 개도 계약

| 부품 | PREOPEN | GRASP | RELEASE |
|---|---:|---:|---:|
| HBM | 25 | 18 | 25 |
| PM | 30 | 25 | 30 |
| GPU | 70 | 65 | 70 |
| CAP/SMD | 18 | 12 | 17 |
| IND | 21 | 14 | 20 |
| VRM | 30 | 24 | 28 |

0~100 개도 명령값이며 mm, 힘, 손목 회전 속도가 아니다. YAML/요청/Backend 준비 계획의 값이 다르면 거절한다. Backend가 호출자의 값을 조용히 바꾸지 않는다.

## 5. 완료 판정과 이벤트 파싱

이벤트 최상위는 `job_id`, `operation_id`, `action`, `phase`, `event`, `error_code`, `message`다. **message는 객체가 아닌 JSON 문자열**이므로 바깥 이벤트와 안쪽 message를 두 번 파싱한다. 일반 오류·구형 저장 이벤트는 문자열일 수 있으므로 내부 JSON 파싱 실패도 처리한다.

| event | Unity 처리 |
|---|---|
| PHASE_STARTED / PHASE_COMPLETED | 내부 진행 표시·아래 GRASP/RELEASE 부착 처리. 다음 로봇 요청을 보내지 않음 |
| OPERATION_COMPLETED | job_id/operation_id/action이 대기 중 요청과 일치할 때 해당 요청 완료 |
| OPERATION_FAILED | 실패 기록, 다음 dispatch 차단, 상태 조회. 새 ID 자동 재시도 금지 |
| REQUEST_REJECTED | 기존 ID의 내용 충돌 등. 기존 요청의 결과를 덮어쓰지 않음 |
| PAUSED / CONTROL_FAILED | 정지 확인 내용 확인, 자동 재개 금지 |
| PAUSE_CONFIRMED / RESUME_CONFIRMED / CONTROL_REJECTED | 별도 retained 제어 계약. 현재 비활성 |

완료 message에 exit_pose, exit_tcp_mm_deg와 검사 근거가 포함될 수 있다. Pick 종료는 TrayHome, Place 종료는 slot_retract_100mm다. 물리 보유·정밀 안착 검증 플래그는 false이며 카메라 완료의 physical_placement_verified 역시 false다. **동작 완료를 품질 PASS로 저장하지 않는다.**

phase 문자열은 중간점 개수·실행 방식에 따라 바뀔 수 있다. 모든 이동 phase를 하드코딩하지 않는다. `GRASP`/`RELEASE`와 terminal 이벤트만 의미에 맞게 분기한다. 연속 이동은 한 그룹 단계에서 완료되며 개별 중간점 완료 이벤트는 없다.

## 6. 원래 객체 ID와 실제 그리퍼 부착

이벤트 message의 schema는 `fr5.robot_event_context/v1`이다. 주요 필드:

| 필드 | 의미 |
|---|---|
| server_instance_id, event_sequence | API 프로세스 UUID와 그 프로세스의 증가 이벤트 번호 |
| part_id, source_index, slot_code, order | 준비된 레시피 대응 |
| source_id, tray_registration_id, source_observation_id | 원래 트레이 객체·등록 세대·관측 ID |
| source_cycle_id, plan_sha256 | 원래 장면/실행 계획 |
| attachment_binding_valid | 세 관측 ID의 유효한 대응 여부 |
| feedback | 단계 실제 피드백 검증 근거 |
| production_job_id, unit_id, display_board_id | 명시적으로 제공된 경우만 포함 |

다음 순서로 구현한다.

1. Pick PHASE_STARTED에서 해당 source_id의 Calibration 갱신·삭제·수동 재생성을 잠근다. 준비된 ID와 등록 세대를 함께 대조한다.
2. `action=robot.pick`, `phase=GRASP`, `event=PHASE_COMPLETED`, `attachment_binding_valid=true`, `feedback.continuous_feedback_verified=true`가 모두 맞으면 원래 객체를 **실측 로봇의 그리퍼 Transform**에 부착한다.
3. `action=robot.place`, `phase=RELEASE`, 같은 검증 조건이면 **해당 실제 보드 Transform**으로 옮긴다. 해제 이벤트는 후퇴 완료보다 먼저 올 수 있으므로 다음 요청은 여전히 OPERATION_COMPLETED까지 기다린다.
4. 부모 변경은 `SetParent(parent, true)`로 월드 자세를 보존한다. Ghost에 부착하지 않는다. 소스 객체가 없거나 ID가 모호하면 임의 복제 객체를 만들어 대신 붙이지 않는다.
5. 실패 시 마지막 부모 관계를 유지하고 uncertain 상태로 표시한다. API 상태와 실제 장면을 대조한다.

PREOPEN 완료, MoveGripper RPC 수락, GRASP 시작만으로 부착하지 않는다. 현재 GRASP는 컨트롤러 완료/물체감지 상태1을1초 연속 확인한다. 상태2는 `GRASP_OBJECT_NOT_DETECTED` 사유의 GRIPPER_FAILED이며 자동 상승하지 않는다. PREOPEN/RELEASE는 상태1 또는2를1초 연속 허용한다. 이것은 컨트롤러 피드백 근거이며 실제 물체 보유의 독립 증명은 아니다.

트레이 ID는 기준 셀 앵커로 유지한다. 앞 부품 제거 후 검출 배열 순서가 바뀌어도 원래 source_id로 찾는다. 등록 세대가 바뀌면 예전 대응을 재사용하지 않는다. 애매한 대응은 id=null이며 옛 스냅샷에 없는 ID를 새로 생성하지 않는다.

중복 처리는 `(server_instance_id, event_sequence)` 및 operation별 처리 상태로 관리한다. sequence가 작다는 이유만으로 아직 처리하지 않은 terminal/GRASP/RELEASE를 버리지 않는다. 이미 placed인 객체를 늦은 GRASP로 재부착하지 않는다. API 재시작 후 과거 journal 재생에는 과거 server_instance_id가 남을 수 있다.

## 7. 상태 조회·재전송·재연결

Trigger의 `response.success=true`는 API 응답 성공일 뿐 동작 허가가 아니다. `response.message` JSON에서 다음을 확인한다.

| 상태 필드 | 확인 내용 |
|---|---|
| hardware_execution_enabled | 현장 실기 활성 설정 |
| state_fresh, robot_health_clear | 최신 피드백과 건강 상태 |
| robot_mode, tool_num, work_num | AUTO=0, Tool1, User0 |
| robot_motion_done, gripper_feedback_valid | 팔 정지=1 및 유효 그리퍼 피드백 |
| active_operation | 현재 작업 ID/action, 유휴면 null |
| held_candidate | 보유 후보. null만으로 실제 빈 그리퍼를 입증하지는 않음 |
| recovery_required | 부분 실패/복구 필요 여부 |
| vision_plan_sha256 | Backend가 받은 준비 계획 해시 |
| prepared_execution | job_id/source_cycle_id/plan_sha256/execution_context/parts 식별자 |
| event_context | server_instance_id/event_sequence/last_event/attachments/terminal_operations |
| continuous_transfer_enabled | 현재 API 연속 이동 설정 |
| control | retained 지원/차단/재개 가능 상태 |
| observed_unix | 상태 응답 생성 시각 |

현재 capability 문자열은 `step-cycle-20260908`, event_context_revision은 `attachment-callbacks-v1`이다. 문서 날짜가 바뀌었다고 새 capability 문자열을 기대하지 않는다. `continuous_driver_revision=per-command-blend-v1`은 로컬 `--check`가 드라이버 조회 후 합쳐 출력하는 값이며, 기본 `/real/robot/status` 응답 필드로 가정하지 않는다.

- 동일 operation_id + 동일 내용 재전송: 진행 중 원래 작업에 합류하거나 저장 terminal 재전달. 실제 명령을 반복하지 않는다.
- 동일 ID + 다른 내용: 거절. 기존 결과를 대체하지 않는다.
- 통신 timeout: 실패 확정이나 다음 단계 허가가 아니다. 다음 dispatch를 차단한 채 상태를 조회하고 같은 ID/내용으로 대조한다.
- API 프로세스/등록 세대 변경 또는 recovery_required: 새 Pick으로 우회하지 않는다. 실패 기록을 유지하고 현장 상태와 대조한다.
- attachments 상태는 reserved/attached/placed이며 uncertain 및 physical_holding_verified/precision_placement_verified를 함께 읽는다. API 재시작 후 이전 부착 상태를 자동 복원했다고 가정하지 않는다.

## 8. 정지와 재개

### 현재 사용할 취소/정지

`/real/robot/pause`에 Bool true를 게시하면 활성 로봇 동작의 취소/정지를 요청한다. 요청 즉시 Unity가 다음 dispatch를 막는다. Bool false는 재개 명령이 아니다. 활성 작업이 없으면 별도 PAUSED 응답이 없을 수 있다.

현재 pause 이벤트의 message에서 `stop_verified=true`, `control_mode=legacy_cancel`, `resume_available=false`를 확인한다. `fresh_feedback_verified_stopped`는 새 피드백으로0.5초 정지 확인한 근거다. `stop_not_verified...` 또는 CONTROL_FAILED이면 정지 완료로 표시하지 않는다. PAUSED는 원래 Pick/Place의 성공 완료가 아니다. 이후 terminal과 상태를 함께 대조한다.

### Retained pause/resume — 현재 비활성, 연동 예약 계약

```json
{
  "command": "pause",
  "control_id": "11111111-1111-4111-8111-111111111111",
  "control_sequence": 1,
  "job_id": "f85aeace-5205-4788-ac7a-d202405e26c3",
  "operation_id": "b6e0fe31-072e-48d9-970a-1ffdf47104e4"
}
```

위 다섯 필드만 허용한다. resume은 같은 작업에 새 control_id와 증가 sequence를 사용한다. 동일 ID/내용 재전송은 저장 응답만 재발행한다. 현재 enable_retained_resume=false이며 **연속 이동과 retained resume 동시 사용은 거절**한다. UI에서 재개 가능으로 노출하지 않는다.

별도 시운전 후 활성화할 경우 PAUSE_CONFIRMED의 stop_verified, RESUME_CONFIRMED의 resume_applied를 검증한다. 대상은 robot_arm이며 컨베이어/그리퍼 전체 정지 보장이 아니다. 실패·관측 만료·재시작 상태는 이 기능으로 복구하지 않는다.

## 9. 비전 준비·수명·실행 순서

비전 담당 handler가 보드/트레이/SMD 근접 관측으로 준비된 계획과 원래 셀 기준을 공급해야 한다. 로봇 API 호출만으로 없는 계획을 촬영·생성하지 않는다. real_precision_targets 어댑터는 준비 데이터 전달용이며 자체 촬영 기능은 없다. Unity에서 로봇 실행용 좌표를 만들어 `/real/vision/targets`에 대체 게시하지 않는다.

| 검사 | 현재 값/의미 |
|---|---|
| frozen_unit | 명시적으로 선택. 원래 가장 오래된 관측부터 최대1800초, 이동 중 재검사 |
| live target | 2.5초 |
| Pick 후 제거 영상 | TrayHome 도착 이후의2초 이내 새 영상, 서로 다른 연속3프레임 |
| 제거 대기 | 최대45초 × 3회 영상 대기. 재파지3회가 아님 |
| 로봇 상태 | 250ms 이내의 서로 다른 새 피드백 |
| 그리퍼 전/후 | TCP0.5초 안정 / 그리퍼1초 연속 완료 확인 |

같은 이미지의 timestamp를 새로 붙여 유효기간을 늘리지 않는다. 부품/기판 재배치·교정 변경 시 기존 계획을 재사용하지 않는다. SMD 새 계획은 같은 Unit의 일반20개 Place 완료 후 기존 완료 슬롯과 겹치지 않게 전환한다.

현재 로컬 전체25개 흐름은 GPU → HBM → PM → VRM → IND → CAP이며 총50개 Pick/Place 요청이다. PlaceCamera 촬영 → TrayHome 관측·VRM 정밀측정 → 일반20개 → SMDView 새 근접측정 → CAP5개 → PlaceCamera 결과사진 순서다.

참고 생산 YAML `assembly_integration/config/sequencer_recipe.current.yaml`의 HBM/PM/GPU/CAP/IND/VRM 순서는 별도 계약이다. **real_execution_ready=false를 유지**한다. item_ready/assembly_ready는 Home 복사 placeholder여서 실제 API가 거절하며, 컨베이어/검사/완성PCB 이송 handler와 전체 설비 순서는 별도 연동·실기 검증 대상이다. ready 값을 true로 바꾸는 것만으로 해결하지 않는다.

## 10. 속도와 연속 이동 — 9월 9일 최신

| 구간 | 명령 속도 | 전체 배율 |
|---|---:|---:|
| Pick/Place 높은 수평 이동·손목 회전 | 40 | 40% |
| Pick/Place 전용 긴 상승 구간 | 30 | 40% |
| Pick/Place 근접 구간 | 10 | 40% |
| 카메라 높은 수평 이동·회전 | 40 | 40% |
| 카메라 긴 수직 이동의 근접구간 밖 | 30 | 40% |
| 카메라 출발 직후·도착 직전50mm, 짧은 수직 이동 | 10 | 40% |

Pick/Place의 일반 travel/combined_rotation 기본값25가 별도 구간에 남아 있다. 모든 이동을40으로 바꾼 것은 아니다. 손목 회전40은40°/초가 아니며 실제 각속도는 관절·경로·배율에 따라 달라진다. Unity는 속도 필드를 요청에 추가하거나 로봇의 실제 움직임을 자체 애니메이션 시간으로 판정하지 않는다.

연속 이동은 높이350mm 이상·동일 높이의 검사된 중간점2~3개에만 적용한다. 중간 blend50ms, 끝점0ms 및 최종 새 피드백 대기. 수직·파지·해제·검사·촬영 끝점은 정지한다. API 단계명에는 CONTINUOUS_TRANSFER 또는 CAMERA_CONTINUOUS_TRANSFER가 포함될 수 있다. 큐 일부 수락 후 오류는 StopMotion 요청과 recovery_required로 남기며 자동 재생하지 않는다.

현재 로봇 PC는 continuous_transfer_enabled=true이며 드라이버 per-command-blend-v1을 사용한다. 다른 PC의 기본값/예제는 false다. 실제 곡선 경로 여유·취소/큐 소거·부드러움·시간 단축은 아직 실기 검증 대상이다.

HBM은 정위치 사진 후8개 배치 시험과 현재 XYZ/각도/그리퍼 값이 일치하고 높이 보정−1.0mm를 유지한다. 수동 사진 기반 신규XY/각도 보정은 당시 교차검증0/8로 적용하지 않았다. Unity에서 별도 보정을 더하지 않는다.

## 11. 실측과 Ghost 표시

기존 RealShadowing 실측 연결을 유지한다. `/real/assembly/robot_state`의 schema는 `fr5.assembly_robot_state/v1`, timestamp_unix, state_fresh, joints_deg(도), tcp_mm_deg(mm/도)를 사용한다. state_fresh=false 또는 스트림 단절이면 실측 표시를 stale로 바꾸며 Ghost로 실제 자세를 대체하지 않는다. 한 모델에 기존 writer와 이전 batch ZIP의 measured synchronizer를 중복 부착하지 않는다.

Ghost JointState는 name=[j1..j6], position=라디안, frame_id=base_link다. stage_target은 schema `fr5.ghost_stage_target/v1`, job/operation/action/phase/point_name, target_id, timestamp_ros_ns, positions_deg/rad, visualization_only를 전달한다. Ghost 수신은 실제 명령 수락·도착·충돌 검증이 아니다.

**현재 연속 이동의 Ghost 제한:** 일반 개별 이동은 PortExecutor가 Move 직전 목표를 발행하지만, 연속 그룹의 MoveJ는 하위 robot._service를 직접 호출하여 중간점별 Ghost 발행 경로를 통과하지 않는다. 따라서 연속 그룹의 모든 중간점 Ghost가 온다고 가정하지 않는다. 그룹 진행은 robot 이벤트와 실측으로 표시한다. 이 문서 작업에서 해당 구현은 변경하지 않았다.

종료·실패·취소·재연결 시 지난 작업의 Ghost를 해제한다. 부착은 Ghost 목표가 아니라 위6절의 실제 단계 이벤트로 처리한다.

## 12. Unity 담당 구현 및 인수 확인

1. command/event/status 연결, 두 단계 JSON 파싱, 한 요청씩 실행과 ID별 terminal 매칭.
2. prepared_execution의 실제 source ID/등록 세대를 기존 Calibration 객체에 매핑하고 Pick 시작 시 보호.
3. GRASP/RELEASE 검증 이벤트에 따른 메인 스레드 부모 변경, 중복·지연·실패 처리.
4. timeout/재연결 시 dispatch 차단, 동일 ID 재전송·status 대조, 프로세스 변경 감지.
5. legacy 취소와 retained 재개를 구분하고 현재 재개 버튼 비활성 처리.
6. 실측/Ghost 분리, 연속 그룹 중간점 Ghost 누락을 견디는 표시.
7. 새 부품 없는 모의시험 후 현장 카메라 왕복·취소 정지, 부품1개 Pick/Place, 전체 사이클 순으로 확인.

현재 남은 현장 항목은 새 카메라 속도/연속 이동 검증, VRM3 신뢰도 미달 원인 확인, IND 실제 보유와 컨트롤러 감지 판정의 재확인, 전체25개/정밀 안착 및 생산 설비 통합 검증이다. VRM 기준0.700을 임의로 낮추거나 GRASP 상태2를 성공으로 바꾸지 않는다.

## 13. 로봇 PC 시작 및 자료 위치

```bash
cd /home/juchan-yoon/FR5_robot_control
./run_fr5_assembly_stack.sh preflight &&
./run_fr5_assembly_stack.sh start &&
./run_fr5_assembly_stack.sh check &&
./run_fr5_assembly_stack.sh view
```

view는 로봇 PC 데스크톱에서 통합RQT와 USB휴대폰 화면을 연다. start는 기존 스택을 정리하고 재기동하므로 실행 중 반복하지 않는다. 위 명령은 서비스/화면 시작이며 조립 시작이 아니다. `preflight`는 설치 확인, 스택 `check`는 프로세스와 상태 표시다. 별도 터미널의 `./run_fr5_cycle.sh --check`가 무동작 조립 준비 검사다.

요청/결과: `runtime/robot_operations/` · 경로/그리퍼/검사 근거: `runtime/robot_step_evidence/` · 스택로그: `runtime/assembly_stack/logs/robot_api.log` · 상세 실기: `runtime/assembly_cycles/`.

## 13.1 피드백 타임아웃 수정 (9월 9일 HBM-06 중단 후)

피드백 대기는 시간 만료 판정 전에 최신 상태를 확인한다. 수신 콜백이 계속 정상 갱신되고 검사 스레드만 지연된 경우에는 최신 상태를 검사한다. 수신 간격이 250ms를 넘으면 sequence와 간격을 기록하며, 이후 새 프레임이 도착해도 해당 실행에서는 ROBOT_TIMEOUT으로 중단한다. 최신 상태 나이 250ms, 고장·취소 검사는 유지한다. 타임아웃 reason에 baseline/current sequence, latest_age_ms, wait_elapsed_ms, receive_gap_sequence/sec가 추가된다. Unity 요청 스키마 변경은 없다.

오프라인 720개 테스트 통과 후 API에 적용했다. HBM-06 실제 중단 당시 수신 공백과 검사 스레드 지연을 구분하는 기록이 없어 당시 원인은 확정되지 않았다. 현재 실패 기록·실행 소유권·recovery_required=true를 유지하며 자동 재시도하지 않는다. 전체 사이클 재검증은 아직 수행하지 않았다.

## 13.2 Pick 이후 수직 상승 중간 정지 축소

API Pick은 첫 50mm 저속 상승을 유지하고, 이후 기존 100mm proof 경유 정지 없이 같은 수직선으로 안전 높이까지 MoveL한다. 중간점에서 별도 검사를 하지 않는 API에만 적용하며, 독립 진단 실행의 100mm proof 정지는 유지한다. 동일 XY/자세·상향 순서·직선 조건을 만족할 때만 중간점을 제거하고 전체 변경 경로에 기존 IK 사전 검증을 수행한다. 현재 계획 기준 첫 50mm 속도10%, 이후 Z350까지 clearance_lift30%다. 기존 50→100mm 구간은 travel25%였으며 이제 합쳐진 상승 전체가30%다. 수평 이송40%, 안전 높이 정지 및 촬영 위치/제거 검사, HBM 보정 좌표는 유지한다.

PHASE 번호는 중간점 제거로 달라질 수 있으므로 Unity는 숫자를 고정하지 않는다. 경로·촬영점 보존 검증 포함 전체726개 테스트 통과. 로봇 이동 실증은 아직 수행하지 않았으며 이 변경만으로 모든 방향 전환 정지가 사라지지는 않는다.

## 13.3 TrayHome 근거리 도착 경로 단순화

API Pick에서 안전 높이로 상승한 위치와 TrayHome 상공 간 수평 거리가50mm 이내, 각 자세축의 최단 변화가5도 이내이면 기존 두 중간점+끝점 MoveJ를 단일 수평 MoveL로 바꾼다. 동일 높이350mm 이상을 유지하고 최종 TrayHome 상공 좌표는 동일하다. 그 이후12.12mm 수직 하강과 촬영 위치 정지는 유지한다. 장거리/큰 자세 변화는 기존 연속 큐를 유지한다. 이 개선은 수평→하강을 블렌딩한 것이 아니다.

기존 start settling의 실제 높이/관절기준/정지0.2초 검사를 단일 MoveL에도 적용한다. 현재 high_transfer40%를 사용하고, 마지막 하강10%는 유지한다. API의 중간 PHASE 개수/번호가 줄어들므로 번호를 고정하지 않는다. 위치/회전/장거리 경로 보존 및 안전 높이 차단 통합 검증 포함730개 테스트 통과. 실제 로봇 이동에 의한 부드러움 검증은 미실시다.

## 14. 작성 기준 소스

경로는 FR5_robot_control 저장소 기준이며 이 문서의 본문만으로 연동 계약을 확인할 수 있다. 아래 해시는 문서 작성 시점 소스 식별용이며 별도 API revision 필드가 아니다.

- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_contract.py` — SHA-256 `9461a125c148a2aa5b17af851121f4f4a60aee4f920d2d35b8f4ea2975e7d5e9`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_precision_steps.py` — SHA-256 `57bd968ecf38d1402cd8dcfd48a7fad384a87b081c6e4fec39f38b140f04d4b5`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_ros_node.py` — SHA-256 `7711dbb6c6cf2b4b81abff8d8d1dd0553a4240006dff563d028de417a388f3a6`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_backend.py` — SHA-256 `e02c49a3135d795f0775802b669a215d3df81b6be1487e1e6f2dd7487b393a69`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/robot_event_context.py` — SHA-256 `1c8a942262d5eb3113b17f034898cb55dcdb1165e70c7717db83383e6ac9d4b2`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/continuous_transfer.py` — SHA-256 `2d55ce6671a814aeb8002448517c8bf8030962a852e4bd5b1fe3fb49842fa26e`
- `ros2_ws/src/fr5_process_sequences/fr5_process_sequences/real_vision_adapter.py` — SHA-256 `9d2a451c086111c5fa4c37bef0b5ac8ce1016b9ea538fa9ac5704bc44c95a43a`
- `vision_assembly/scripts/cycle_camera_stage.py` — SHA-256 `dbd4992ddb6443a2b06846f720e90c4890bff9e1351e9a563b547ae328fce128`
- `assembly_integration/config/sequencer_recipe.current.yaml` — SHA-256 `5ca8cbec96af1549004be680e4ff8f535aeab50db397491e0a1ee1545f1f952c`

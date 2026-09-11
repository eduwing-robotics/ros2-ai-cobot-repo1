# 전체 조립 계약 v2 — 구현 및 검증 범위

2026-09-09. 요구서 검토 후 사용자의 진행 지시로 작업 소스에 구현했다. 운영 install, 실행 중 API, 하드웨어 설정에는 배포하지 않았다. 로봇·그리퍼 명령을 보내지 않았다. 최종 인수 완료가 아니다.

## 구현한 범위

- 기존 v1 진단 API와 구분되는 `fr5.assembly_execution/v2` 추가. 같은 `/real/assembly/command` 및 `/real/assembly/event`의 std_msgs/msg/String JSON을 사용한다. Action 패키지나 병행 기동 경로를 추가하지 않았다.
- Start는 한 execution_id/production_job_id/unit_id의 full 25개만 요청할 수 있다. 임의 좌표·단계·profile은 받지 않는다. 기존 내부 launcher를 호출한다. 외부 생산 DB에 접근하지 않는다.
- 같은 ID/같은 요청은 만료된 장면 확인이나 변경된 현재 revision 때문에 재기동하지 않고 기존 기록을 반환한다. 다른 내용으로 같은 ID는 EXECUTION_ID_CONFLICT다.
- production_recipe_bindings.json의 product_id/production_recipe_version/robot_recipe_revision/expected_slots 대응을 확인한다. 중복·잘못된 슬롯 대응은 거절한다. 현재 실제 대응 파일을 생성하지 않았다. Main_Server&DT에서 제품 코드 HBM-ACCELERATOR-PACKAGE-BOARD와 생산 레시피 assembly-r1을 확인했으며, 운영 대응 파일과 robot_recipe_revision 설정은 배포 때 대조해야 한다.
- Start에는 명시적 operator_id, 대상 execution_id, confirmed_unix, 확인 scope가 필요하다. 120초 이내 확인만 새 Start에 사용한다. 이는 운영자의 확인 진술이며 실물 검증·신원 인증을 대신하지 않는다. 현재 120초는 구현값으로 상대측과 합의해야 한다.
- 기존 실행 잠금과 owner lease를 사용한다. 미해결 생산 기록이 있으면 lease가 없어도 개별 API 실행을 차단한다. API 재시작은 기존 실행을 다시 시작하지 않는다.
- 현재/특정 실행 조회 및 not_found, 실행 당시 recipe_revision과 현재 revision 분리, 생성 시각과 상태 변경 시각 분리, 실행별 event_sequence를 제공한다. JSON 기록은 fsync 및 원자 교체로 저장하며 자동 삭제하지 않는다. 기록을 수동 삭제한 뒤 중복 방지를 보장하지 않는다.
- 전체 완료는 정확한 슬롯 집합과 중복 없음, 두 phase의 고정 계획 해시·실행 식별·상태, 종료 PlaceCamera 촬영, 최종 API의 fresh/health/정지/보유 없음 확인을 모두 요구한다. exit 0 또는 25개라는 개수만으로 성공하지 않는다.
- terminal 저장 후 늦은 monitor나 발행 예외가 결과를 바꾸지 않는다. 물리 정밀 안착은 false, inspection_pass는 null이다.
- 개별 이벤트는 `event=ROBOT_EVENT`와 원본 robot_event로 전달한다. 개별 OPERATION_COMPLETED와 전체 EXECUTION_COMPLETED는 다르다. 기존 원본 식별·피드백 판단으로 만든 attachment snapshot을 실행 기록에 저장한다. 다른 실행/과거 epoch/중복 순번의 이벤트를 적용하지 않는다.
- 연속 MoveJ의 모든 중간 목표도 각 dispatch 전에 Ghost로 발행한다. 반복 phase의 target_id는 고유하며 instance+sequence를 제공한다. J1..J6, rad/deg, base_link를 유지한다. 전송 실패 자체로 로봇을 정지시키지 않는다.
- Ghost 최신 목표 조회와 종료/실패/정지 시 무효화, production execution_id 연결을 추가했다. 촬영/조립의 실제 사전검사 명령 경로 해시 motion_plan_version을 Ghost와 실행 근거 파일에 함께 저장한다. stage_target은 기존 v1에 필드가 추가된다. target_id는 opaque 식별자로 사용해야 하며 예전 operation:phase 문자열을 조합해 추정하면 안 된다.
- 저장소의 Unity Ghost 예제는 sequence/instance/무효화 처리와 TargetValid를 추가했다. 실제 Unity 프로젝트에서 컴파일/Scene 연결 검증은 하지 않았다.

## 연결 형식

`/real/assembly/status`는 기존 std_srvs/srv/Trigger 형식을 유지한다. 기존 v1 응답에 production_contract와 ghost_snapshot이 추가된다. 특정 생산 실행은 command/event의 조회 요청을 사용한다.

```json
{"schema":"fr5.assembly_execution/v2","action":"assembly.status","execution_id":"11111111-1111-4111-8111-111111111111"}
```

execution_id를 생략하면 현재 상태다. 조회는 실행·정지·reset을 발생시키지 않는다.

Start 형식 예시(실행용으로 게시하지 않음):

```json
{
  "schema": "fr5.assembly_execution/v2",
  "action": "assembly.start",
  "execution_id": "11111111-1111-4111-8111-111111111111",
  "production_job_id": "AGREED_PRODUCTION_JOB_ID",
  "unit_id": 1,
  "product_id": "AGREED_PRODUCT_ID",
  "production_recipe_version": "AGREED_PRODUCTION_RECIPE_VERSION",
  "robot_recipe_revision": "MATCH_CONFIGURED_ROBOT_REVISION",
  "scene_confirmation": {
    "operator_id": "ACTUAL_OPERATOR_ID",
    "execution_id": "11111111-1111-4111-8111-111111111111",
    "confirmed_unix": 0,
    "scope": "empty_gripper_empty_pcb_full_tray_fixed_fixture"
  }
}
```

이 예시의 시각 0과 미합의 문자열은 거절되는 예시다. 상수 true나 현재 시각을 자동 주입하여 현장 확인을 대체하면 안 된다. 수락 결과는 request_accepted=true와 replayed 여부를 포함한다. 최종 결과는 Status/Event로 확인한다.

Start capability는 `enable_production_assembly`(기본 false)와 유효한 레시피 대응이 모두 있어야 true다. 이번에 이 파라미터를 활성화하지 않았다. 기존 v1 assembly.start는 계속 별도 비활성이다. 실제 생산 활성화 전 아래 미완료 범위 및 단계별 실기 승인을 처리해야 한다.

## 남은 구현·합의·시험

1. **전체 보존형 Pause/Resume 소스를 구현했다.** 실행 ID와 프로세스를 유지하고 새 actuator 전송을 차단한 뒤 PauseMotion과 fresh 정지 피드백을 확인한다. Resume은 같은 pause_control_id, 증가하는 control_sequence, 살아 있는 실행기, 동일 recipe/pose/gripper/보유 식별과 유효 관측을 요구한다. 단계 사이와 API 대기의 시계도 Pause를 반영한다. 기본 enable_whole_cycle_pause=false이며 연속 이동은 buffered_pause_verified까지 필요하다. 실제 컨트롤러 큐 보존 실기 시험은 남아 있다. 기존 취소 경로를 재개로 바꾸지 않았다.
2. 기존 v1 assembly.stop 및 개별 안전정지/복구 경로는 유지한다. 생산 execution_id는 내부 job_id와 operation_id에 대응한다. v2 취소 명령은 추가하지 않았으며 cancel=false다.
3. 생산 제품·레시피 대응값, 장면 확인 주체/유효 시간, timeout/QoS/보존 정책을 상대측과 합의해야 한다. 현재 command depth10, event depth50, robot_event 수신 depth100, state 2Hz 및 measured 10Hz는 기존 ROS 설정을 기반으로 한다. 전체 이벤트는 진행 변경과 robot 이벤트에 따라 발행되며 최대 발행량 규약은 미확정이다.
4. Ghost의 재계획 이력 및 실제 Unity 네트워크 재접속·stale 표시를 포함한 최종 인수 시험이 남아 있다. 일반/SMD 계획 해시는 각각 생성 후 고정된다. 두 계획 생성 전 plan_complete=false다.
5. 최종 판정은 ROS 시각화 이벤트 수신과 무관하게 원본 backend snapshot의 25개 placed/binding/uncertain 상태를 직접 검증한다. 마지막 시각화 이벤트 누락과 불확실 binding의 모의 시험은 통과했다. 장기간 재접속과 실제 terminal 경합 시험은 남아 있으며 물리 보유 증명으로 확대하지 않는다.
6. 외부 ASSEMBLY_SEQUENCER의 Real YAML 실행을 제거하고 한 Unit의 전체 조립 호출·영속 ID·상태 조회·Pause/Resume·검사/DB 후속 흐름을 연결했다. Mock YAML은 유지한다. 기존 도메인 5 Endpoint를 재사용하도록 Sequencer 도메인 43의 공개 service/feedback을 연결한다. 컨베이어/후처리의 실제 공개 API 어댑터는 원본 브랜치에도 없으며 아직 미연결이다. 이 상태에서는 Job claim 전에 NOT_READY다. 로봇 내부 YAML은 유지한다.
7. 실제 정상 한 사이클, 정지/재개, 연결 단절·API 재시작·외부 Sequencer 재시작에 대한 물리 인수는 미실시다. 요구서의 12개 인수 항목 전체 통과를 주장하지 않는다.

## 검증

소스 PYTHONPATH를 지정한 로봇 패키지 및 launcher 모의 테스트 **292개 통과**. 추가 dispatch 차단·Pause 시계/실행 주인 검증 묶음 **10개 통과**(중복 포함). 외부 Sequencer 전체 호출/Mock/DB writer 모의 회귀 **49개 통과**. 양쪽 실제 계약 클래스를 연결한 Start→Pause→Resume→전체 완료 모의 테스트 **1개 통과**. 실제 DB·로봇 I/O를 사용하지 않았다. 운영 install을 변경하지 않았다.

C# 예제는 소스 검토만 수행했다. Python 테스트는 실제 I/O 없이 모의 실행기/피드백을 사용한다.

## 최신 Unity 전달 문서

[전체 조립 연동 안내](UNITY_WHOLE_ASSEMBLY_HANDOFF_KO_20260909.md)를 함께 전달한다. 이 문서의 구현은 로컬 소스이며 GitHub Main_Server&DT에 push하거나 실행 중 서비스를 재시작하지 않았다.

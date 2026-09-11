# 로봇 전체 조립 Start 운영 반영 — 2026-09-09 19:06 KST

## 상대측 전달 요약

로봇 서버에 전체 조립 v2를 배포하고 생산 레시피를 등록했다. 19:06 KST 실제 /real/assembly/status 조회에서 아래 상태를 확인했다. 18:58의 진단 전용 서버와 달라졌다.

```json
{
  "hardware_execution_enabled": true,
  "production_contract": {
    "schema": "fr5.assembly_execution/v2",
    "status": "idle",
    "capabilities": {"start": true,"pause": false,"resume": false,"status": true,"event": true,"cancel": false,"final_acceptance_complete": false},
    "current_recipe_revision": "20260909_smd_restore_successful_gripper_profile",
    "equipment_busy_or_unresolved": false
  }
}
```

중요: 최상위 schema/supported_actions/capabilities/scope는 기존 진단 v1 전용이다. 최상위 supported_actions에 assembly.start가 없다는 이유로 생산을 거절하지 않는다. 생산 준비 여부는 **production_contract.schema와 production_contract.capabilities.start**를 읽는다. 실제 hardware_enabled, freshness, busy/recovery, 제품 대응 및 현장 확인도 별도로 검증한다.

## 통신

기존 Endpoint와 ROS_DOMAIN_ID=5를 유지한다.

- 조회: /real/assembly/status, std_srvs/srv/Trigger. 응답 message JSON의 production_contract 사용.
- 요청: /real/assembly/command, std_msgs/msg/String.data JSON.
- 결과: /real/assembly/event, std_msgs/msg/String.data JSON.
- schema: fr5.assembly_execution/v2.

실제 command/event 왕복은 assembly.status 요청과 not_found 응답으로 확인했다. 실제 Start는 보내지 않았으며 전체 동작 완료 callback은 모의 테스트를 통과한 상태다. 새 서버 피드백에서 로봇 정지, 보유 후보 없음, 실행 작업 없음, 복구 요구 없음도 확인했다.

## 전체 조립 요청 예시

아래는 형식 예시다. UUID/Unit/확인자를 실제 생산 정보로 대체한다. confirmed_unix=0은 거절되며, 운영자의 실제 준비 확인 시각을 넣어야 한다. 임의 좌표, HBM만 실행하는 profile, 개별 Pick/Place 배열을 보내지 않는다.

```json
{
  "schema": "fr5.assembly_execution/v2",
  "action": "assembly.start",
  "execution_id": "11111111-1111-4111-8111-111111111111",
  "production_job_id": "22222222-2222-4222-8222-222222222222",
  "unit_id": 1,
  "product_id": "HBM-ACCELERATOR-PACKAGE-BOARD",
  "production_recipe_version": "assembly-r1",
  "robot_recipe_revision": "20260909_smd_restore_successful_gripper_profile",
  "scene_confirmation": {
    "operator_id": "ACTUAL_OPERATOR",
    "execution_id": "11111111-1111-4111-8111-111111111111",
    "confirmed_unix": 0,
    "scope": "empty_gripper_empty_pcb_full_tray_fixed_fixture"
  }
}
```

동일 Unit의 execution_id와 전체 요청은 영속 보관한다. 동일 ID/동일 내용은 중복 실행하지 않고 기존 상태를 반환한다. 현장 확인은 120초 이내여야 하며, 그리퍼 비움·빈 PCB·25개 트레이·고정 지그 확인을 자동 true로 대체하지 않는다.

상태 조회:

```json
{"schema":"fr5.assembly_execution/v2","action":"assembly.status","execution_id":"11111111-1111-4111-8111-111111111111"}
```

전체 완료는 event=EXECUTION_COMPLETED, status=motion_complete_awaiting_physical_verification에서 같은 실행/생산 식별자, expected_slots/completed_slots 정확한 25개 집합, non-smd/smd 계획 해시, stop_verified, held_candidate 없음, recovery_required=false를 대조한다. 수락과 개별 ROBOT_EVENT 완료는 전체 완료가 아니다. inspection_pass=null이며 실제 후속 검사에서 PASS를 결정한다.

## 여전히 남은 범위

Pause/Resume 코드는 구현했지만 실제 컨트롤러 연속 이동 큐 인수가 끝나지 않아 현재 capability=false다. UI에서 활성화하지 않는다. 기존 안전정지/복구 수단은 유지한다.

로봇 Start 지원을 활성화한 것으로 컨베이어 이동·도착·검사·배출 연결까지 완료됐다는 뜻은 아니다. 외부 담당자는 벨트 도착 후 위 v2 전체 조립을 요청하고, 전체 완료 후 검사 이송을 진행한다. 실제 벨트/검사 완료 callback을 사용한다. 로봇 내부 Pick/Place 순서를 Sequencer에 재구현하지 않는다.

로봇 설치 및 서버는 갱신했다. 외부 Sequencer/Unity의 원격 실행 PC에는 이번 도구로 배포하지 않았다. 원격 GitHub push도 하지 않았다.

## 구현 위치와 검증

로봇: FR5_robot_control/ros2_ws/src/fr5_process_sequences/fr5_process_sequences/assembly_execution.py 및 assembly_cycle_ros.py.
레시피: FR5_robot_control/assembly_integration/config/production_recipe_bindings.json.
기동: FR5_robot_control/scripts/run_real_robot_api.sh, 로컬 config/ksmc.env의 KSMC_PRODUCTION_ASSEMBLY=true.
외부 참고 클라이언트: fr5-main-dt-integration/ASSEMBLY_SEQUENCER/src/assembly_sequencer/assembly_sequencer/assembly_execution_client.py 및 real_backend.py.

배포 전 모의 테스트 296개 통과. 설치 패키지 빌드 성공. 실제 Status 및 동작 없는 v2 command/event 조회 성공. 원본 설치·기동 설정과 전후 상태 근거는 runtime/deployments/20260909-190441-production-api에 보관했다. 실제 조립 Start와 장비 이동은 수행하지 않았다.

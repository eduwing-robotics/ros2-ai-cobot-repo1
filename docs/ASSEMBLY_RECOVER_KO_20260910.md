# 반복 시험용 공통 조립 복구

현장 런처와 Unity 모두 같은 조립 서버의 `assembly.recover`를 사용한다.
정상 완료(`motion_complete_awaiting_physical_verification`)는 원래 새 ID 시작을 차단하지 않는다. 복구 명령을 호출해도 완료 결과와 미검사 상태를 유지한다.
실패(`recovery_required`)는 조건 확인 후 `failed_recovered`로 전환한다. 실패 원인·부품 진행 기록·기존 Start 요청은 보존한다. 같은 ID Start는 계속 이전 결과를 반환하며 새 실행이 아니다.

## 현장 명령

부품을 정리하고 빈 그리퍼, 빈 기판, 트레이 부품, 고정구를 직접 확인한 뒤:

```bash
cd /home/juchan-yoon/FR5_robot_control
./recover_assembly.sh --confirm-scene-ready --operator-id juchan
```

성공 응답: `request_accepted=true`, `recovery_applied=true`, `recovery_required=false`, `retry_requires_new_execution_id=true`.
그다음 새 실행 ID와 새 현장 확인으로 한 사이클을 시작한다. 복구 명령은 자동 Start나 물리적 원점 복귀를 하지 않는다.

## Unity

`/real/assembly/command` (`std_msgs/String`)에 다음 JSON 전송. 시간은 예시 상수가 아니라 전송 시점 Unix 초, ID는 현재 실패/완료 실행 ID로 채운다.

```json
{
  "schema": "fr5.assembly_execution/v2",
  "action": "assembly.recover",
  "execution_id": "현재 실행 UUID",
  "scene_confirmation": {
    "operator_id": "현장 작업자 ID",
    "execution_id": "현재 실행 UUID",
    "confirmed_unix": 0,
    "scope": "empty_gripper_empty_pcb_full_tray_fixed_fixture"
  }
}
```

`confirmed_unix`는 120초 이내의 실제 현장 확인 시간이어야 한다. 현장 확인 UI에서 작업자 확인 후 생성한다. 수신은 `/real/assembly/event`; `execution_id`로 대응하고 `recovery_applied=true`를 확인한다. 이전 실행의 `event=EXECUTION_FAILED`는 보존될 수 있으므로 이 값만으로 복구 실패라고 판단하지 않는다. 새 Start에는 반드시 새 execution_id를 사용한다.

로컬 v1 명령도 지원하며 `schema=fr5.assembly_cycle/v1`, `execution_id` 대신 최상위 `operation_id`를 사용한다. 확인 객체 안의 execution_id는 동일한 실행 UUID이다.

## 수동 중지 후 복구 (확장)

부딪힘 등으로 수동 중지했다면 충돌 원인을 제거하고, 파지 부품을 제거해 제자리로 복원하고, 빈 기판·트레이·고정구까지 다음 시험 상태로 정리한 뒤 같은 명령을 사용한다. `--confirm-scene-ready` 또는 Unity의 scene_confirmation은 이 현장 확인을 뜻한다.

현재 실행 worker가 종료되고 정지 피드백이 안정적인 경우 `abnormal_stop`만 남은 상태는 `ResetAllError()` 후 새 피드백으로 해제를 검증한다. 같은 실행의 종료된 하위 작업 기록에서 파지/복구 요구를 정리하고, 종료된 소유권을 감사 폴더로 이동한다. API 재시작 없이 적용된다. 기존 실패 이벤트와 요청 fingerprint는 유지한다.

비상정지, 안전문·안전영역 신호, 충돌/서보 등 다른 활성 오류, 움직이는 로봇, 오래된 피드백, 살아 있는 작업자 프로세스, 다른 실행의 미해결 기록, 결과를 모르는 intent 기록은 차단한다. 물리적 문제를 먼저 해결해야 한다.

로봇 이동·그리퍼 열기·자동 재개·새 Start는 하지 않는다. 이 복구는 기존 사이클 이어하기가 아니라 새 ID 테스트 준비다. 감사 기록은 `runtime/manual_stop_recovery/`에 남긴다.

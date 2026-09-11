# 생산 실행 중지·이어하기·취소

동일 `/real/assembly/command` (`std_msgs/String`), 스키마 `fr5.assembly_execution/v2`를 사용한다.

```json
{
  "schema": "fr5.assembly_execution/v2",
  "action": "assembly.cancel",
  "execution_id": "현재 실행 UUID",
  "control_id": "이 제어 요청의 새 UUID",
  "control_sequence": 1
}
```

control_sequence는 실행별 증가 정수다. 재전송은 같은 control_id와 같은 내용을 사용하며 물리 동작을 반복하지 않는다. 제어 응답의 execution_id/control_id로 대응한다.

취소는 `CONTROL_ACCEPTED` 후 명령 전송 차단, StopMotion, worker SIGINT, 정지 피드백 검증 순서다. `CANCEL_STOP_CONFIRMED`는 로봇 정지가 검증됐다는 뜻이며 작업 프로세스 종료나 현장 복구 완료를 뜻하지 않는다. 최종 `recovery_required` 상태와 worker 종료를 확인하고 부품을 정리한 뒤 `assembly.recover`를 호출한다. 취소는 같은 실행 이어하기를 허용하지 않는다. 제어 실패는 `CONTROL_FAILED`, stop_verified=false로 반환한다.

일시정지는 action=`assembly.pause`, 이어하기는 action=`assembly.resume`이며 이어하기 요청에는 현재 pause의 control_id를 `pause_control_id`로 추가한다. 동일 실행·실행 프로세스·좌표·그리퍼·파지 정체성·관측/설정 유효성을 검증한다.

현재 연속 이동 큐의 실제 PauseMotion/ResumeMotion 검증 전에는 pause/resume capability를 활성화하지 않는다. 저수준 robot control의 retained_resume_not_commissioned와 생산 whole-cycle capability는 별도다. 생산 UI는 production_contract.capabilities를 사용한다.

실기 검증 항목: 빈 그리퍼와 정리된 작업영역에서 승인된 짧은 경로를 사용하고, 큐가 있는 이동 도중 정지 후 0.5초 이상 좌표 유지, 동일 실행 재개 후 원래 종점 도달 및 큐 순서 유지, 재전송에 따른 중복 동작 없음, 정지 중 취소 후 새 이동 없음, 상태 변경/프로세스 상실 시 재개 거부를 확인한다. 실패 시 활성화하지 않는다.

## 활성화한 모드

`pause_behavior=after_dispatched_motion`: 이미 컨트롤러에 전송된 이동/큐가 끝나고 0.5초 이상 정지한 뒤 PAUSE_CONFIRMED를 반환한다. 즉시 제동이나 비상정지가 아니다. 다음 동작 전송과 실행 프로세스는 대기하며, 이어하기는 동일 실행의 다음 동작을 허용한다. 컨트롤러 PauseMotion/ResumeMotion은 사용하지 않는다. 즉시 중단은 assembly.cancel을 사용한다.

빈 그리퍼·J1 최대 1.5도·속도 1% 실기에서 대기·이어하기·정지 중 취소 및 중복 제어 무동작을 확인했다. 초기 컨트롤러 직접 PauseMotion 모드는 정지 검증에 실패하여 활성화하지 않았다. 취소 후 abnormal_stop은 정상 복구 절차로 해제한다. 원시 피드백 및 제어 증거: runtime/pause_commission_20260910/.

환경 설정 KSMC_WHOLE_CYCLE_BOUNDARY_PAUSE=true로 생산 모드를 활성화한다. 저수준 retained resume는 계속 비활성이다. 생산 UI는 production_contract.capabilities의 pause/resume/cancel과 pause_behavior 및 해당 실행 resume_available을 사용한다.

# 로봇 콜백·부착 연동 API 전달서 (2026-09-08)

## 범위 및 적용 상태

FR5_robot_control의 로봇 Backend, 로컬 Python API 클라이언트, 트레이 관측 식별자 전달을 구현했다. Main_Server&DT는 3e4b399bda22497b51752261a633499cb1eaa90e를 읽기 전용으로 참고했다. Unity 및 해당 브랜치의 Sequencer 코드는 수정하지 않았다.

실장비 적용/시운전 완료를 뜻하지 않는다. 실행 중인 API/검출기를 재시작하지 않았으며 로봇·그리퍼 동작 명령도 보내지 않았다. enable_retained_resume 기본값은 false다. 실기 검증 전에는 true로 변경하지 않는다. 기존 real_execution_ready 설정도 유지한다.

현재 IND-01 GRIPPER_FAILED는 이미 실패한 작업이다. 이 기능으로 재개하거나 실패 기록/보유 후보를 지워서는 안 된다. 별도의 실제 상태 확인과 복구가 필요하다.

## 이벤트

기존 /real/robot/event (std_msgs/String)의 JSON 최상위 필드 job_id, operation_id, action, phase, event, error_code, message를 유지한다. message는 JSON 문자열이며 다음 필드를 추가한다.

- schema: fr5.robot_event_context/v1
- server_instance_id: API 프로세스별 UUID, event_sequence: 해당 프로세스의 증가 번호
- part_id, source_index, slot_code, order
- source_id: 실행 스냅샷이 보존한 원래 tray parts[].id
- tray_registration_id, source_observation_id, source_cycle_id, plan_sha256
- attachment_binding_valid: 세 관측 식별자가 모두 유효하고 중복되지 않을 때 true
- feedback: 해당 단계의 실제 피드백 검증 결과
- production_job_id, unit_id, display_board_id: 호출자가 명시적으로 제공한 경우만 포함

job_id는 Unit 실행 UUID다. 생산 Job UUID로 해석하지 않는다. 스냅샷 execution_context는 execution_job_id가 job_id와 일치해야 하며 production_job_id와 양의 정수 unit_id는 함께 제공한다. 외부 실행에서 생산 ID를 추측하지 않는다.

Pick PHASE_STARTED부터 source_id의 Calibration 갱신/삭제/수동 재생성을 보호해야 한다. robot.pick / GRASP / PHASE_COMPLETED이고 feedback.continuous_feedback_verified=true일 때만 실제 그리퍼 Transform으로 부착한다. robot.place / RELEASE / PHASE_COMPLETED의 같은 검증 이후 실제 보드 Transform으로 옮긴다. Unity는 SetParent(parent, true)로 월드 자세를 보존해야 한다. PREOPEN, RPC 수락, PHASE_STARTED를 부착 완료로 해석하지 않는다. 미확인 식별자에는 새 물체를 만들어 대신 붙이지 않는다.

GRASP는 현재 컨트롤러 물체 감지 상태 1을 1초 연속 확인한다. 상태 2는 GRASP_OBJECT_NOT_DETECTED로 실패하고 자동 상승하지 않는다. PREOPEN/RELEASE는 완료 상태 1 또는 2를 허용한다. 컨트롤러 피드백은 물체의 실제 보유나 정밀 안착을 직접 입증하지 않는다.

다음 작업은 일치하는 job_id/operation_id/action의 OPERATION_COMPLETED에서만 진행한다. 단계 이벤트는 완료 응답이 아니다. 중복 이벤트를 재적용하지 않는다. 제어 응답과 작업 스레드의 발행 순서가 겹칠 수 있으므로 전역 sequence가 작다는 이유만으로 아직 처리하지 않은 작업 terminal/GRASP/RELEASE를 버리지 않는다. 이미 placed인 물체를 늦은 GRASP로 다시 붙이지 않는다.

## 원래 트레이 ID

검출기는 기준 트레이 픽셀의 고정 앵커를 사용해 세션 동안 셀 식별자를 유지한다. 앞 부품이 사라져 planner instance_index가 압축돼도 뒤 부품의 id가 바뀌지 않는다. ID는 이제 opaque 문자열(part_type:UUID)이다. ID에서 순번을 파싱하지 말고 source_index를 별도로 쓴다. 12px 범위의 유일한 대응만 허용하며 애매한 대응은 id=null이다. 이것은 기준 셀 대응이지 물체의 물리적 동일성 증명이 아니다.

검출기 재시작/등록 세대 변경은 별도의 등록 식별자로 구분한다. 캡처 → frozen snapshot → API target → 이벤트로 원래 식별자를 전달한다. 옛 스냅샷에 없는 ID는 생성하지 않는다. 좌표, 파지 높이, planner 순번은 이 식별자 로직으로 변경하지 않는다.

## 상태 조회와 재연결

기존 /real/robot/status에 event_context_revision, event_context, prepared_execution, control, control_topic, observed_unix를 추가했다. event_context에는 프로세스 UUID, sequence, attachments, terminal_operations가 있다. attachment state는 reserved/attached/placed이며 실패 시 마지막 상태를 유지하고 uncertain=true가 된다. physical_holding_verified 및 precision_placement_verified는 false다.

prepared_execution은 현재 준비된 job_id, plan hash, 생산 매핑(있을 때), 각 부품 관측 식별자를 제공한다. 재연결 시 현재 실행·프로세스·등록 ID를 대조한다. API 재시작 후 예전 부착 상태를 임의 복원하지 않는다. recovery_required 또는 epoch 불일치이면 UI의 마지막 부모 관계를 유지한 채 별도 상태 대조가 필요하다.

## 일시정지/재개 (기본 비활성)

/real/robot/control (std_msgs/String) 요청은 아래 다섯 필드만 허용한다.

```json
{"command":"pause","control_id":"11111111-1111-4111-8111-111111111111","control_sequence":1,"job_id":"22222222-2222-4222-8222-222222222222","operation_id":"33333333-3333-4333-8333-333333333333"}
```

resume은 같은 실행/작업 ID에 새 control_id와 더 큰 control_sequence를 사용한다. 동일 control_id·내용 재전송은 저장 응답만 재발행하며 명령을 반복하지 않는다. 충돌, 오래된 sequence, 다른 작업, 실패한 작업, 복구 필요 상태는 거절한다.

PAUSE_CONFIRMED는 PauseMotion 수락 후 새 피드백으로 로봇 팔의 0.5초 정지를 확인한 응답이며 message.stop_verified=true다. RESUME_CONFIRMED는 같은 작업 문맥에서 ResumeMotion 수락 뒤 도착한 새 정상 피드백을 확인한 응답이며 resume_applied=true다. 컨베이어나 그리퍼 전체 정지를 의미하지 않는다(robot_scope=robot_arm). CONTROL_FAILED/CONTROL_REJECTED는 성공이 아니다.

정지 요청 직후 클라이언트의 다음 dispatch를 막는다. Backend도 retained barrier로 기존 작업을 유지하고 새 작업을 막는다. 정지 중 원래 관측 유효시간은 계속 흐른다. 재개 시 원래 문맥 검증, 피드백/그리퍼 변화, 보유 후보와 감지 상태, 레시피/슬롯 설정(precision 작업)을 확인한다. 실패·관측 만료·프로세스 재시작은 새 Pick/Place로 우회하지 않는다. Backend 동작 timeout에서 확인된 pause 시간만 제외한다.

로컬 SequencerRobotClient.control()은 Future와 제어 ID/sequence를 대응하고 제어 timeout 이후에도 dispatch 차단을 유지한다. 늦은 성공 응답으로 자동 해제하지 않는다. 외부 Sequencer는 상태 조회·명시적 조정 및 자신의 작업 timeout 예산 관리가 필요하다. 기존 runRecipe의 호출자 wall-clock timeout은 자동 연장되지 않는다. Job/Unit RUNNING 유지와 Unity 메인 스레드 처리도 외부 담당 구현 사항이다.

기존 /real/robot/pause Bool true는 취소/정지 경로다. 이를 retained resume 가능 정지로 취급하지 않는다.

## 검증 및 남은 항목

로봇 패키지 및 vision_assembly 테스트: 595개 모두 통과. 최초 발견한 PM-03/04의 0.5mm 차이는 저장 누락이나 새 좌표 오류가 아니라, 9월 7일 fixture가 사용자 승인한 9월 8일 PM 추가 하강(-0.5mm)을 반영하지 않은 테스트 문제였다. docs/CODEX_HANDOFF.md의 “PM4 배치 높이 추가 −0.5mm 저장” 기록 및 변경 전 백업으로 확인했다. 원본 실측 fixture는 보존하고 기대 Z에 승인된 -0.5mm만 명시적으로 적용했다. 실제 레시피·좌표 설정은 바꾸지 않았다.

Unity 담당자가 Calibration 보호 및 실제 부모 변경, 생산 실행 매핑, 제어 handshake/재연결 처리를 연결해야 한다. 실장비의 정지·같은 operation 재개 시운전, 현재 IND 복구는 별도로 남아 있다. 본 문서는 자동 사이클 실행 허가가 아니다.

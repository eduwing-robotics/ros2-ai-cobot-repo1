# 전체 조립 계약 요구서 검토 및 구현안

작성: 2026-09-09. 입력: /home/juchan-yoon/Downloads/ROBOT_ASSEMBLY_CONTRACT_REQUIREMENTS_KO_20260909.md.
상태: 코드 대조 검토 완료. 아래 v2는 제안이며 제공 중인 API가 아니다. 이번 검토는 실행 코드 변경, API 재시작, 로봇 기동을 포함하지 않는다.

## 결론

책임 분리는 타당하다. 로봇 내부의 기존 전체 사이클을 재사용하고, 외부 Sequencer는 Unit·생산 순서·검사·DB만 소유하는 방향을 채택할 수 있다. 다만 현재 구현을 Start 활성화만으로 전환하면 안 된다. 전체 실행에 걸친 상태 보존 Pause/Resume, 실행 식별 결합, 완료 증거 집계, 전체 Ghost 제공이 별도 구현 대상이다. 현재 최종 인수 조건은 미충족이다.

## 코드 대조

| 요구 | 현재 근거 | 판정 / 필요 작업 |
|---|---|---|
| 한 Unit 전체 Start | assembly_cycle_ros.py가 AssemblyCycleController(... allow_batch_start=False) 생성 | 공개 생산 Start 비활성. v1 진단 의미 유지하고 생산 계약 버전 분리 |
| 기존 실행기 재사용 | assembly_cycle_launcher.py의 api_workflow/run_cycle | 보드 촬영→트레이 촬영→VRM→일반20→SMD 촬영/5개→종료사진 재사용 가능 |
| 실행/생산/레시피 식별 | assembly_cycle_api.py는 job_id/operation_id/revision/profile 사용 | execution_id, production_job_id, unit_id, 생산 레시피 대응을 명시적으로 고정해야 함 |
| 멱등성/재시작 | operation_id별 JSON 저장, 동일 요청 재사용, 재시작 시 recovery_required | 기본 토대 있음. 생산 실행과 제어 요청에도 적용하고 보존 정책 명문화 |
| 단일 실행 잠금 | robot_execution_guard, launcher.lock, step_operation.lock, step_api_owner.json | 기존 잠금 재사용. Start 수락 경쟁 및 API 재시작 중 살아 있는 자식 실행을 포함해 검증 필요 |
| Pause/Resume | assembly.stop은 SIGINT. retained_robot_control은 개별 operation 대상 | 전체 실행 보존형 Pause가 아님. 촬영/대기/단계 사이/연속 그룹까지 상태를 보존하는 제어 필요 |
| 연속 이동 재개 | continuous_transfer.py에서 retained enabled일 때 명시 거절 | 옵션을 켜서 해결 불가. 컨트롤러 큐 정지·제거 및 완료 경계 확인 후 미완료 구간 재계획을 검증해야 함 |
| 특정 실행 Status | Trigger는 입력 없이 현재 snapshot만 반환 | 같은 command/event 방식의 조회 요청을 추가하고 unknown/not_found 구분. 현재 상태와 특정 실행 결과 분리 |
| 전체 완료 | _monitor는 완료 슬롯 고유 개수와 launcher 상태 검사 | 정확한 슬롯 집합, 계획/레시피 대응, 종료 정지·보유 상태를 결합해야 함. 개수만 같아도 잘못된 슬롯일 수 있음 |
| 전체 Event | 기존 cycle 이벤트는 snapshot 중심 | 실행별 event_sequence/instance/terminal, 동작·관측·원본 객체의 일관된 결합 필요 |
| Ghost 전체 목표 | 일반 목표 발행 존재. continuous_transfer는 robot._service 직접 호출 | 연속 중간점 누락. 촬영 이동 포함 모든 dispatch의 목표 발행 및 실행 ID/순서/계획 버전 추가 |
| Ghost 재접속 | stage_target은 volatile, target_id는 operation:phase | 최신 유효 목표 snapshot 및 정지/실패 시 무효화 필요. 재계획/동일 phase 반복의 target_id 충돌 방지 |
| 실측 | /real/assembly/robot_state에 fresh/관절/TCP/그리퍼 제공 | 측정 시각·발행 시각 분리, 실행 상관 정보 추가 |
| 부착/분리 | 기존 인계 문서의 binding 및 continuous feedback 조건 존재 | 전체 실행 snapshot에 마지막 확정 관계·uncertain·이벤트 버전 결합 필요 |
| 외부 YAML 제거 | 이 검토는 FR5 저장소만 조사 | 외부 Sequencer/Unity/DB 참조 조사 및 Mock 회귀는 별도 통합 작업. 로봇 내부 YAML 삭제 대상 아님 |

코드 경로는 ros2_ws/src/fr5_process_sequences/fr5_process_sequences/ 아래 assembly_cycle_api.py, assembly_cycle_ros.py, retained_robot_control.py, continuous_transfer.py, real_ghost.py 및 vision_assembly/scripts/assembly_cycle_launcher.py를 기준으로 한다. 기존 인계 문서 unity_integration/UNITY_ROBOT_API_HANDOFF_KO_20260909.md의 9·11절과도 일치한다.

## 제안하는 구현 경계

기존 command/event 전송을 유지한다. 신규 Action 패키지와 별도 병행 기동 경로는 현재 필요하지 않다. 생산용 스키마 fr5.assembly_execution/v2를 명시적으로 구분하고 v1 진단 요청을 생산 시작으로 해석하지 않는다. 다음 예시는 구현 전 합의안이다.

Start 입력: schema, action=assembly.start, execution_id(UUID), production_job_id, unit_id(양의 정수), product_id, production_recipe_version, robot_recipe_revision, scene_confirmation_id. 임의 관절/TCP/부품별 단계 배열은 받지 않는다. scene_confirmation_id는 현장 확인 주체·대상 설비·Unit·유효 시간과 결합하며 아직 제공되는 기능이 아니다. 현재 confirm_scene_ready=true를 클라이언트가 자동 생성하지 않는다.

Start 응답: accepted/rejected, execution_id, error_code, reason, request fingerprint. 수락은 완료가 아니다. 초기 plan은 null이며 촬영 후 non-smd/smd 계획 해시 목록과 버전을 같은 실행에 추가한다. SMD 계획이 나중에 생성되는 현재 흐름을 고려하여 하나의 초기 해시를 완성된 전체 계획으로 표시하지 않는다.

Pause/Resume 입력: execution_id, control_id, sequence, command. 제어 응답은 accepted/applied/rejected를 구분하고 stop_verified, evidence, resume_available, recovery_required를 함께 제공한다. 정지 중 그리퍼 개폐를 새로 명령하지 않고 보유 상태/관측 유효성을 검증한다. 취소는 기존 별도 기능으로 유지한다. API 재시작 후에는 자동 재개하지 않는다.

Status 결과: 계약·capability·instance·생성/측정 시각, 실행 식별, 고정 레시피/계획 목록, expected/completed_slots, 내부 단계, stop/held/attachment/recovery, 최신 이벤트 순번, 최신 Ghost snapshot, 마지막 terminal. 조회는 제어를 발생시키지 않는다.

완료 조건: 정확한 expected_slots 집합과 completed_slots 집합 일치, 실패 없음, 모든 필요 단계 완료, 최신 종료 정지/보유 상태 검증. 결과는 조립 동작 완료이며 검사 PASS가 아니다. physical_holding_verified 및 physical_placement_verified는 독립 검증 없으면 false/unknown을 유지한다. 종료 위치는 현재 after_photo의 PlaceCamera 흐름과 맞춰 계약에 명시하고 TrayHome이라고 가정하지 않는다.

## 구현 순서와 검증

1. 생산 실행 기록/식별/슬롯·레시피 대응/조회/terminal 일관성부터 오프라인 시험한다. 같은 ID 재전송, 다른 내용 충돌, BUSY, 재시작 후 차단, 잘못된 슬롯·진단 완료의 성공 오인 방지를 포함한다.
2. 기존 실행기의 촬영부터 종료까지 전체 제어 위치와 잠금 소유권을 연결한다. 일시정지를 SIGSTOP이나 자식 재실행으로 구현하지 않는다. 보존형 정지 중 단계 timeout의 처리도 구분한다.
3. 모든 명령 목표의 Ghost 선발행, 순서·ID·계획 결합, 재접속/무효화, 부품 관계 snapshot을 구현·시험한다. 시각화 전송 실패 자체는 동작 정지 조건으로 추가하지 않는다.
4. 연속 이동의 실제 정지·큐 상태·잔여 실행 재개를 실기 검증한다. 해결 전 capability.resume=false로 공개하며 최종 완료로 표기하지 않는다. 이동 속도나 연속 이동 설정을 조용히 변경하지 않는다.
5. 모의 공개 계약으로 Sequencer/Unity를 연결해 인수 1~12를 대응시킨다. DB·Mock 시험은 해당 저장소에서 수행한다. 대체 경로 검증 후 Real YAML 실행 경로를 삭제한다.
6. 문서 요구대로 단계별 사용자 확인 후 실제 기동 시험한다. 이번 문서 검토는 실기 기동 승인이 아니다.

일정은 1~3의 기존 코드 변경량과 4의 컨트롤러 재개 검증 결과를 확인한 뒤 산정한다. 현재 날짜를 납품 완료일로 약속하지 않는다. 기록 보존은 자동 삭제 없이 중복 방지 기록 유지, 보관·삭제 후 재사용 거부 정책을 함께 설계하는 안을 권장한다. QoS/발행량/timeout 수치는 구현 및 상대측 연결 시험 후 확정해야 한다.

## 인수 상태

문서의 12개 인수 항목 전체에 대해 새 생산 계약 통합 시험은 미실시다. 기존 개별 API의 테스트 통과를 새 전체 실행 계약의 통과로 옮겨 적지 않는다. 특히 4(Pause/Resume), 7(전체 Ghost), 10(재시작/원격 실행 확인), 12(외부 YAML 제거/Mock)는 전환의 핵심 선행 조건이다.

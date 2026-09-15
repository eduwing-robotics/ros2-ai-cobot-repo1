> **19:06 KST 운영 갱신:** 로봇 v2 배포 및 생산 레시피 등록 완료, production_contract.capabilities.start=true를 실제 확인했다. 아래 미배포 설명은 이전 시점 기록이다. Pause/Resume은 실기 인수 전 false이며 외부 Sequencer/컨베이어는 별도다. 최신 문서: ROBOT_PRODUCTION_START_DEPLOYED_KO_20260909.md.

# Unity 전체 조립 연동 전달 — 2026-09-09

## 적용 상태

GitHub Main_Server&DT의 확인 기준 커밋은 `3e4b399bda22497b51752261a633499cb1eaa90e`다. 아래 추가 구현은 로컬 소스에 있으며 원격 브랜치 push, 운영 install 배포, 실행 중 API 재시작은 하지 않았다. 정상 실기 사이클과 컨트롤러 큐 Pause/Resume 인수는 미실시다.

기존 ROS-TCP Endpoint(로봇 PC, TCP 10000, ROS domain 5)를 재사용한다. 새 Endpoint를 띄우지 않는다. Endpoint가 실행 중인 것과 Unity가 현재 연결된 것, 생산 API가 준비된 것은 각각 확인해야 한다.

## 연결과 책임

Unity → 기존 Endpoint/domain 5 → 공개 Sequencer service proxy → Real Sequencer/domain 43 → 로봇 전체 조립 API/domain 5.

Sequencer가 Job·Unit·검사·DB를 소유한다. 로봇이 PCB 한 장의 촬영·계획·25개 픽/배치·최종 확인을 소유한다. Real Sequencer는 YAML 좌표나 개별 MoveJ/Pick/Place를 보내지 않는다. Mock YAML은 유지한다.

| Endpoint | Type | 용도 |
|---|---|---|
| /unity/assembly/start | fairino_msgs/srv/RemoteCmdInterface | 생산 Start, Pause, Resume, 현장 확인, Status |
| /unity/assembly/feedback | std_msgs/msg/String | 생산 Job/Unit 상태 |
| /real/assembly/command | std_msgs/msg/String | Sequencer가 사용하는 로봇 전체 실행 v2 요청 |
| /real/assembly/event | std_msgs/msg/String | 로봇 전체 실행 상태/이벤트 |
| /real/assembly/status | std_srvs/srv/Trigger | 응답 message의 production_contract 및 ghost_snapshot |

## Unity 요청

Service 요청 `cmd_str`은 실제 LF를 포함한 `real\n` 접두사 뒤에 JSON을 붙인다. 여기서 \n은 두 글자를 보내라는 뜻이 아니라 줄바꿈이다. 응답 JSON은 `cmd_res`다. 읽기 status는 접두사 없이도 허용한다.

```json
{"command":"start","job_id":"<등록된 Job UUID>","recipe_version":"assembly-r1"}
```

```json
{"command":"pause","job_id":"<현재 Job UUID>"}
```

```json
{"command":"resume","job_id":"<현재 Job UUID>"}
```

```json
{"command":"status"}
```

각 Unit이 조립 위치에 도착하면 현장 준비 확인을 기다린다. 빈 그리퍼, 빈 PCB, 전체 부품 트레이, 고정 지그를 운영자가 확인한 후 해당 Unit에만 다음 요청을 보낸다. 시각은 실제 확인 시점 Unix 초이며 현재 120초 유효하다. Unit이 바뀌면 새 확인이 필요하다. 자동 true/자동 확인 버튼 호출로 대체하지 않는다.

```json
{"command":"confirm_scene","job_id":"<현재 Job UUID>","unit_id":1,"operator_id":"<확인자>","confirmed_unix":0}
```

0은 형식 예시이며 실제 요청에서는 거절된다. Unity는 생산 요청을 Sequencer로 보내고 같은 Unit의 robot Start를 별도로 중복 발행하지 않는다.

## 로봇 v2 제어 계약

schema는 `fr5.assembly_execution/v2`. execution_id는 Sequencer가 Job UUID와 Unit 번호로 결정하여 영속 기록한다. 요청 수락은 완료가 아니다. 개별 `ROBOT_EVENT`의 OPERATION_COMPLETED도 전체 완료가 아니다.

```json
{"schema":"fr5.assembly_execution/v2","action":"assembly.pause","execution_id":"<실행 UUID>","control_id":"<새 제어 UUID>","control_sequence":1}
```

```json
{"schema":"fr5.assembly_execution/v2","action":"assembly.resume","execution_id":"<같은 실행 UUID>","control_id":"<새 제어 UUID>","control_sequence":2,"pause_control_id":"<확인된 Pause 제어 UUID>"}
```

같은 control_id 재요청은 동일 내용이어야 한다. 오래된 순번이나 이전 Pause 세대의 Resume은 거절한다. Pause는 control_applied와 stop_verified 확인 후 표시한다. Resume은 resume_applied를 확인한다. Status의 capabilities와 resume_available을 버튼 가용성에 반영한다. 통신 timeout은 정지 확인이 아니며, 새 execution_id로 재실행하지 않고 원래 ID의 상태를 조회한다. API/Sequencer 재시작 후 자동 재생하지 않는다.

전체 완료는 `EXECUTION_COMPLETED`, 정확한 25개 completed_slots, 두 계획 해시, 정지·보유 없음 등 실행 근거를 검증한다. `inspection_pass=null`, `physical_placement_verified=false`다. 합격은 후속 실제 검사에서 결정한다.

## Ghost와 실측

기존 Ghost 수신 경로를 유지한다. 목표는 실제 명령 전송 전에 발행하며 연속 이동 중간 목표도 포함한다. target_id는 불투명 고유 ID로 취급하고 문자열을 조합하여 추정하지 않는다. server instance/sequence로 오래된 데이터와 재접속 데이터를 구분한다. frame_id와 rad/deg 단위를 명시적으로 처리한다.

Pause/종료/실패 시 목표 무효화를 적용하고 TargetValid=false를 화면에 반영한다. 확인된 Resume에서만 재활성화된다. 최신 목표는 /real/assembly/status의 ghost_snapshot으로 복원한다. 실측 freshness와 age를 표시하며 오래된 값을 현재 위치로 표시하지 않는다. attachment는 식별/피드백 근거이며 물리 보유·정밀 안착 증명으로 확대하지 않는다.

C# 수신 예제: FR5_robot_control/unity_integration/Assets/Scripts/RealGhostStageReceiver.cs. 실제 Unity 프로젝트 컴파일과 Scene 연결은 별도 검증해야 한다.

## 운영 적용 전 남은 사항

- 생산 레시피 대응 파일 및 Sequencer robot_recipe_revision을 일치시킨다. 확인된 제품 코드는 HBM-ACCELERATOR-PACKAGE-BOARD, 생산 레시피는 assembly-r1이다. 로봇 revision은 로봇 설정/Status에서 대조한다.
- enable_production_assembly와 enable_whole_cycle_pause 기본값은 false다. 연속 이동 Pause/Resume은 buffered_pause_verified 실기 검증 설정도 필요하다. 소프트웨어 테스트만으로 활성화하지 않았다.
- 원본 브랜치에 컨베이어·후처리 실제 API 어댑터가 없다. 서비스 이름뿐 아니라 타입·요청/응답·도착/실패 식별 계약을 받아 연결해야 한다. 현재 prepare는 이 부분이 없으면 Job claim 전에 NOT_READY로 거절한다.
- 운영자의 단계별 확인 후 정지 상태 검증, 제한된 이동 Pause/Resume, 연속 이동 큐 보존, 네트워크/프로세스 단절, 전체 25개 사이클 순으로 실기 인수한다. 현재 로봇 명령을 보내지 않았다.

## 검증 근거

로봇/launcher 모의 테스트 292개, 외부 Sequencer 모의 회귀 51개 통과. 실제 양쪽 계약 클래스를 연결한 Start→Pause→Resume→전체 완료 모의 시험 1개 통과. 추가 Pause barrier/시계 검증도 통과했다. 이 수치는 중복을 합산한 총계가 아니며 실제 Unity·DB·하드웨어 인수를 뜻하지 않는다.

## 추가 검증 및 Unity 상태 필드

생산 feedback/status의 scene_confirmation_required=true는 해당 Unit의 현장 확인을 기다리는 상태다. 로봇 Pause와 구분하여 표시한다. robot_execution_id는 전체 완료 시 연결된 로봇 실행 ID를 제공한다. Real 완료 슬롯은 로봇 결과의 실제 슬롯 식별 목록을 보존한다. API 재시작 후 과거 제어 확인으로 성공 처리하지 않으며 재개 대신 상태 조정이 필요하다.

외부 회귀 51개, 로봇 Pause/관측 만료/시계 및 양쪽 계약 연결 묶음 12개가 통과했다. 실기 시험 결과가 아니다.

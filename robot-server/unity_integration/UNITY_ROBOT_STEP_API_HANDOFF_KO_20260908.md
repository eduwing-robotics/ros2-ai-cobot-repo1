# Unity / Sequencer 단일 로봇 동작 API — 2026-09-08

## 이번 수정과 합의

기준: `UNITY_ROBOT_STEP_API_REQUIREMENTS_KO_20260908.md`.
이전 `/real/assembly/command`의 `assembly.start`는 전체 25개/부품군을 실행하므로
Sequencer의 YAML 한 단계 계약과 맞지 않았다. Real bridge에서 batch start를 차단했다.
기존 `robot.move_joint`, `robot.pick`, `robot.place`를 사용한다. 새 로봇 명령 토픽을 만들지 않았다.

운영자 합의 예외: **Pick 내부에 TrayHome 이동과 트레이 제거 검사를 포함한다.**
이동 검증에 성공한 기존 경로를 재사용하기 위한 명시적 예외이며,
YAML의 다음 Home/준비점 이동을 대신 완료했다고 처리하지 않는다.

- Pick: 요청된 한 부품 접근 → 사전 개방 → 하강 → 닫기 → 50/100 mm 상승 →
  안전 높이 경유 TrayHome → 연속 3장의 새 영상에서 해당 셀 제거 검사 → 완료 응답.
- Place: 해당 Pick과 일치하는 요청만 허용. 현재 실측 자세에서 안전 높이와
  기존 회전 방향을 따라 해당 슬롯 접근 → 하강 → 해제 → 슬롯 위 100 mm 후퇴 → 완료 응답.
- 두 동작 모두 다음 부품이나 다음 YAML 동작을 자동 실행하지 않는다.
- CAP = 기존 SMD / `right_white_brown`. SMD의 셀 검사는 TrayHome의 등록된
  전체 트레이 픽셀로 수행하며, 근접 카메라 픽셀을 대입하지 않는다. 기준이 없으면 거절한다.

## 소유권과 실행 경계

Sequencer가 YAML을 고정하여 Job/Unit, 부품 순서, 동작 순서, DB 상태를 관리한다.
로봇 Backend는 한 요청의 경로·보정·그리퍼·검증만 수행한다.
`conveyor.move_to`, `vision.resolve_targets`, `inspection.run`은 각 담당 handler가 실행한다.

현재 계약의 `job_id`는 **한 물리 Unit 실행에 유일한 UUID**로 할당하고 Sequencer가
생산 Job/Unit ID에 매핑한다. 생산 Job ID를 여러 PCB에 그대로 재사용하지 않는다.
`operation_id`는 그 Unit의 개별 로봇 동작에 유일한 UUID이다.
`order`는 YAML 행 순서, `source_index`는 부품 종류별 1부터 시작하는 트레이 인덱스다.
한 물리 트레이 관측을 새 Unit에 재사용하는 것도 거절한다.

YAML의 gripper 값은 요청 그대로 검증한다. 교정된 장비 profile과 다르면
`INVALID_REQUEST`로 거절하며 JSON 값으로 몰래 바꾸지 않는다.
현재 검증 경로는 approach/retract 100 mm를 지원한다. 다른 값은 거절한다.
안전 높이 350 mm 이상, 마지막 50 mm 저속, 글로벌 속도 40%, 이동 25%/수직 10%,
J6 -178~178도, 관절 변화 95도 이하, soft limit 여유 10도를 유지한다.

## 기존 요청 / 이벤트

- `/real/robot/command`: `std_msgs/msg/String`, JSON.
- `/real/robot/event`: `std_msgs/msg/String`, JSON.
- `/real/robot/pause`: `std_msgs/msg/Bool`, true.
- `/real/robot/status`: `std_srvs/srv/Trigger`, response.message에 JSON.

HBM-01 Pick 예시 (UUID는 Unit/동작마다 Sequencer가 발급):

```json
{
  "job_id": "f85aeace-5205-4788-ac7a-d202405e26c3",
  "operation_id": "b6e0fe31-072e-48d9-970a-1ffdf47104e4",
  "action": "robot.pick",
  "part_id": "HBM", "slot_code": "HBM-01", "order": 1, "source_index": 1,
  "approach_dz_mm": 100.0, "retract_dz_mm": 100.0,
  "pregrasp_opening_percent": 25,
  "grasp_opening_percent": 18, "release_opening_percent": 25
}
```

Place는 `action=robot.place`, 새 operation_id, 동일 job/part/slot/order/source_index,
동일 approach/retract/release를 보낸다. pregrasp/grasp 필드는 보내지 않는다.
`robot.move_joint`는 `joint_point` 6개 **도 단위**와 `point_name`을 사용한다.
절대 TCP 좌표는 Unity에서 로봇 명령에 넣지 않는다.

이벤트 기존 필드: `job_id`, `operation_id`, `action`, `phase`, `event`,
`error_code`, `message`.
`PHASE_STARTED`/`PHASE_COMPLETED`는 내부 단계 진행이다.
**`OPERATION_COMPLETED`만 해당 호출의 성공 종료**다. 수락이나 한 단계 완료로 넘어가지 않는다.
`OPERATION_FAILED`는 실패이며 새 operation_id로 자동 재시도하지 않는다.
`REQUEST_REJECTED`는 기존 ID와 내용 충돌이며 원래 실행 결과를 덮어쓰지 않는다.

완료 message에는 JSON 문자열로 다음 근거를 제공한다. 외부 이벤트 필드를 새로 만들지 않았다.
- `exit_pose`: Pick `TrayHome`, Place `slot_retract_100mm`.
- `exit_tcp_mm_deg`: 마지막 완료 실측 [x,y,z,rx,ry,rz], mm/deg, base_link.
- `evidence`: 제거 영상 시각·프레임 수 또는 해제/후퇴 피드백 근거.
- `physical_holding_verified=false`, `precision_placement_verified=false`.

**그리퍼 닫힘 + 트레이에서 사라짐은 실제 손 안에 잡혀 있다는 완전한 증명이 아니다.**
완료는 합의된 제어·제거 검사 통과다. 낙하, 정밀 안착, 품질 PASS를 보증하지 않는다.
제거 검사 실패 시 Place/다음 동작을 차단하고 원래 실패 이유를 남긴다.

Pause RPC 수락과 실제 정지는 구분한다. PAUSED 또는 실패 message의
`fresh_feedback_verified_stopped`는 새 피드백에서 0.5초 정지 확인,
`stop_not_verified...`는 정지를 확인하지 못했다는 의미다. PAUSED라는 이름만으로
실제 정지를 단정하지 않는다. 최초 실패 원인은 정지 후처리 오류 앞에 보존한다.

## 비전 준비와 유효기간

기존 고정 fixture 실행기는 TrayHome/PlaceCamera/SMD 근접 촬영 결과로 한 계획을 만든다.
이를 매 Pick/Place마다 최신 프레임인 것처럼 다시 timestamp를 붙이지 않는다.

Backend 소유 `real_precision_targets` 어댑터에 `--frozen-unit`을 명시하면,
`vision.resolve_targets`가 준비한 해당 Unit의 계획·트레이 셀 기준·교정 해시를
기존 내부 `/real/vision/targets` 토픽에 한 번 전달한다.
이것은 Unity의 로봇 명령 계약이 아니라 Backend 비전 준비 데이터다.

```bash
ros2 run fr5_process_sequences real_precision_targets \
  --project-root "$KSMC_ROOT" \
  --snapshot /absolute/path/to/current_unit_snapshot.json \
  --sequence /absolute/path/to/frozen_recipe.yaml \
  --job-id <UNIT_EXECUTION_UUID> \
  --output /absolute/path/to/resolved_targets.json \
  --frozen-unit --publish
```

- frozen Unit: 원래 source_age를 포함한 가장 오래된 촬영 시각부터 최대 **1800초**.
  Pick/Place 시작과 매 이동 전에 재검사한다. 계획/그리퍼/슬롯/hand-eye 변경은 거절한다.
- 이 옵션이 없는 live target: 기존 **2.5초** 유지. 오래 걸리는 Pick 뒤의 Place를
  연결하려면 명시적 frozen Unit 준비가 필요하다.
- 제거 검사 영상: 도착 이후 취득한 **2초 이내** 영상, 서로 다른 연속 3프레임.
  최대 45초 × 3회 영상 대기이며, 물리적 재파지 3회가 아니다.
- 로봇 피드백: 250 ms 이내의 서로 다른 새 표본. 그리퍼 전 TCP 0.5초 안정,
  그리퍼 후 1초 연속 완료 피드백을 확인한다.
- fixture/부품을 사람이 다시 놓거나 교정을 바꾸면 기존 Unit 계획을 폐기하고 새로 준비한다.
  이 lifetime은 움직이는 부품 추적을 보장하지 않는다.

추가 카메라 촬영/컨베이어 이동을 Pick/Place가 숨겨 시작하지 않는다.
현재 `vision.resolve_targets`의 현장 촬영 orchestration과 Unity Sequencer handler 연결은
별도 통합 항목이다. 어댑터 CLI 자체는 촬영하지 않는다.

## Ghost와 실측 표시

기존 `RealFairinoSdkGhostSolver → GhostMaster.PreviewJoints`를 유지한다.
`/real/ghost/target`: sensor_msgs/JointState, name=[j1..j6], position=라디안,
header.frame_id=base_link. 실제 사용할 IK 목표를 각 Move RPC 직전에 발행한다.
계획 전체를 한꺼번에 발행하지 않는다. Ghost 전달 여부는 실행 허가 조건이 아니다.

기존 보조 `/real/ghost/stage_target`: std_msgs/String, schema `fr5.ghost_stage_target/v1`.
`job_id`, `operation_id`, `action`, `phase`, `point_name`,
`target_id=operation_id:phase`, `timestamp_ros_ns`, `positions_deg`, `positions_rad`,
`joint_names`, `visualization_only=true`, `preview_only=false`를 사용한다.
반복 midpoint도 phase 앞 일련번호가 달라 target_id가 중복되지 않는다.
선형 이동 전체 궤적이나 충돌 검증 결과가 아니라 해당 이동의 끝 관절 자세다.

`/real/ghost/command`, `/real/ghost/event`는 기존 joint preview 요청/결과이며
실제 로봇 동작을 실행하지 않는다. Sequencer 생산 실행은 `/real/robot/command`다.

실측은 기존 RealShadowing 연결을 유지한다. 기존 `/real/assembly/robot_state`의
joints_deg는 **도**, tcp_mm_deg는 mm/deg다. 이 이름은 진단 호환용으로 남는다.
이전 batch ZIP의 별도 measured-model writer를 함께 붙여 중복 구동하지 않는다.
Unity는 operation/phase와 `/real/robot/event`를 연결하여 중단·실패·완료·재접속 시
과거 Ghost를 해제하고, 실측 stale이면 추정 표시하지 않아야 한다.
이 Unity 상태 연결과 실제 화면 타이밍은 아직 현장 연동 시험 대상이다.

## 재전송 / 복구 / 현재 준비 상태

동일 ID+동일 내용: 실행 중에는 기존 진행에 합류, 완료 후에는 저장된 결과 재전달.
재접속 시 같은 명령을 같은 ID로 재전송해 결과를 조회한다. 새 ID를 자동 발급하지 않는다.
작업 intent/result는 `runtime/robot_operations`, 상세 경로/실측/검사 근거는
`runtime/robot_step_evidence`에 저장한다. 파일 기록 실패는 성공으로 처리하지 않는다.
중간 재시작/불명확한 결과/부분 수행 실패는 자동 재개하지 않는다.
현장 상태를 맞춘 뒤 기록을 보존하는 유지보수 복구와 새 Unit 준비가 필요하다.
자동 recovery/reset API를 추가하지 않았다.

현재 테스트: 단일 Pick/Place, 기존 경로 동등성, GPU 제거 실패, CAP 셀 검사,
입력 불일치, 중복 방지, restart, Ghost, 기존 planner/launcher 회귀를 모의 검증했다.
**새 API를 통한 실물 Pick/Place와 전체 YAML 사이클은 아직 실행하지 않았다.**

`sequencer_recipe.current.yaml`은 `real_execution_ready: false`를 유지한다.
item_ready/assembly_ready는 Home 복사본이므로 실제 API가 해당 이름을 거절한다.
`robot.transfer: assembled_pcb`도 미검증으로 거절한다.
ROS Sequencer의 전체 runRecipe는 ready=false를 실행하지 않는다.
개별 Pick/Place API 구현 완료와 전체 생산 레시피 commissioning 완료를 구분한다.

후속 변경: 로컬 `run_fr5_cycle.sh`도 이제 개별 단계 API를 사용한다.
기존 성공 범위 25개 조립과 전체 설비 YAML은 구분한다. 최신 설명은
`FR5_FULL_CYCLE_STEP_API_20260908.md`를 참조한다.
이전 `UNITY_ASSEMBLY_CYCLE_API_20260908.zip`은 생산 연동 자료로 사용하지 않는다.

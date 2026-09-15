
## 전체 런처 단계 API 연결 완료 — 2026-09-08 후속

`run_fr5_cycle.sh --execute`와 모든 --profile 테스트는 이제 개별 Pick/Place API를 호출한다.
PlaceCamera/TrayHome/SMDView 이동도 기존 안전 경로를 Backend에서 실행한다.
기존 성공 범위인 일반20+SMD5 및 최종 사진이며, PCB transfer/컨베이어/검사 PASS는 포함하지 않는다.
전체 소유권 잠금과 같은 Unit의 일반20 완료→SMD 새 측정 계획 전환을 구현했다.
301개 회귀 테스트, 25개/50요청 모의 통합, 실제 런처 --check 통과. 실물 새 사이클 미실행.
상세: docs/FR5_FULL_CYCLE_STEP_API_20260908.md
증거: runtime/full_cycle_step_api_20260908/
이전 “로컬 런처 직접 실행” 기록은 아래의 과거 상태이며 최신 실행 경로가 아니다.

---

## 2026-09-08 Unity 단계 API 수정 적용

사용자 합의: 기존 실기 경로를 재사용하며 Pick은 한 부품 파지 후 TrayHome 제거 검사까지
포함하고 종료한다. Place는 별도 요청으로 한 슬롯 해제/100mm 후퇴까지만 수행한다.
다음 부품/다음 YAML 이동은 Sequencer가 결정한다.

- 새 internal real_precision_steps.py를 기존 /real/robot/command에 연결.
- 기존 full-cycle build/preflight/move 경로와 방향/높이/속도 검증 재사용.
- CAP/SMD도 단일 동작 지원; TrayHome 셀 제거 검사는 물리적 holding proof와 구분.
- 기존 Ghost 토픽 사용, 내부 이동마다 실제 IK 목표 발행, frame=base_link.
- operation intent/terminal 영속화, 재전송 중복 방지, 부분 수행 실패/재시작 자동 복구 금지.
- frozen Unit source 1800초를 명시적으로 선택; live target 2.5초, 제거 영상 2초 유지.
- batch assembly.start는 Real bridge에서 차단. 로컬 run_fr5_cycle.sh는 batch API
  강제 연결 전의 진단 실행기로 복구했으므로 생산 Sequencer 실행과 혼동하지 않는다.
- real_execution_ready=false 유지, Home placeholder ready/PCB transfer는 아직 미검증.
- 회귀 테스트 284개 통과, colcon 빌드 및 유휴 API 재시작 완료. 로봇 움직임 시험은 안 함.

자료: unity_integration/UNITY_ROBOT_STEP_API_20260908.zip
상세: unity_integration/UNITY_ROBOT_STEP_API_HANDOFF_KO_20260908.md
증거: runtime/step_api_requirements_review_20260908/

---

# Codex Handoff — KSMC FR5 Vision Assembly Cell

## 새 런처 사이클 25개 동작 완료 — 2026-09-08 10:43

사용자가 현장 준비 완료를 확인한 뒤 그리퍼 활성화 및 전체 `--check`를 통과하고 `./run_fr5_cycle.sh --execute`를 실행했다. `runtime/assembly_cycles/20260908-102057-579195`에서 **단일 런처 호출로13단계·일반20개+SMD5개 배치/해제 동작 완료**, exit0, 10:20:57~10:43:53(22분55.7초). 새 트레이25개는 첫 수집, VRM5는 원래120초 창 안에서81초에 완료, SMD5는 두 번째 측정에서 통과했다. 일반432점/SMD90점 IK와 조립명령597개 기록 일치를 확인했다. HBM08도 이번 실행에서 TrayHome 검사와 배치/해제를 마쳤다. 과거 접촉 원인 해결을 뜻하지는 않는다.

최종 PlaceCamera 이동·사진 저장 후 정지 확인: TCP 약 `[36.948,-449.134,321.342,179.998,0.001,-180.000]`, AUTO0/Tool1/User0, 그리퍼17/피드백valid, 오류·충돌·abnormal_stop0. [결과](../runtime/assembly_cycles/20260908-102057-579195/execution_result.json), [최종 사진](../runtime/assembly_cycles/20260908-102057-579195/after/board.jpg), [완료 감사](../runtime/assembly_cycles/20260908-102057-579195/full_cycle_completion_audit.json). 실제 안착에 대한 사용자 확인은 대기 중이다. 기판에는 이번 조립 부품이 있으므로 준비 상태 확인 없이 새 사이클을 시작하지 않는다. 아래 “실제 조립 미실행”은 이번 시작 전의 역사 기록이다.

## 최신 수정·검증 — 2026-09-08

[오늘 일지](../작업일지/2026-09-08.md)와 [수정·검증 보고서](PROJECT_REVIEW_FIXES_2026-09-08.md)를 먼저 확인한다. 사용자 승인 후 최초 검토 R1~R8의 로봇 상태 최신성·보유 불확실성·장애 기록·RGB/depth 관측 일치 및 별도 API/검사 결함을 수정했다. 전체 오프라인 검사와 런처 dry-run 결과는 보고서의 검증 기록을 따른다. R9는 복원용 소스 사본을 남기고 Git 정리/독립 checkout 재현은 후속으로 남겼다.

트레이 검출기와 vision/robot/Unity calibration API만 재시작해 적용했다. driver·D435·보드 영상 프로세스는 유지했다. 실제 새 트레이 관측5개에서 TRACKING/25개 표시와 좌표 계산을 확인했다. 이는 전체 조립 준비·정밀 품질검사 통과를 뜻하지 않는다. 마지막 읽기 조회는 TrayHome/정지1/AUTO mode0/그리퍼 피드백invalid, 오류·충돌0이고 Robot API는 DISARMED다. 이전 조회는 수동mode1이었으며 이 작업에서 모드 전환 명령을 보내지 않았다. 실제 조립은 미실행이다. 재개 전에 현재 상태와 빈 그리퍼·빈 기판·부품 배치·걸림 여부를 다시 확인한다.

컨베이어 보정 허가는 지속 heartbeat(기본 유효시간1초, 같은 발행자의 새 true2회)를 요구한다. 단발 true를 보내던 외부 발행자는 [보정 API 문서](UNITY_BOARD_CALIBRATION_API_KO.md)에 맞춰야 한다. 기존 성공 레시피·방향·좌표·SMD 높이는 보존했다.

`run_fr5_assembly_stack.sh view`는 이제 기존 D435 RQT와 USB 휴대폰 화면을 함께 연다. 기존 휴대폰 화면 재사용과 실패 시 RQT 계속 실행을 검증했다. 오늘 휴대폰 영상3840×2160/약30fps 확인. 세부 증거는 오늘 일지 참조.

아래 9월7일 충돌 인계의 JSON TCP/그리퍼 값에는 최신 로그와 불일치가 있다. 오늘 보고서 R2에 정정 근거를 남겼으며 과거 값을 현재 복구 출발점으로 사용하지 않는다.

## 최종 상태 — 2026-09-07 HBM 마지막 부품 그리퍼 충돌 보고 / 미해결

사용자 보고: “지금 마지막에할때 hbm마지막이 부딪혔거든 그리퍼랑”. 마지막 실행 `runtime/assembly_cycles/20260907-194725-908616`은 **HBM-08 중단** 상태다. GPU-01과 HBM-01~07은 배치 동작 완료 기록이 있으나, 전체 25개 성공은 아니다. HBM-08 배치 완료 기록은 없다.

로그 마지막 검증 단계는 `HBM-08:tray_after_inspect`(파지 후 TrayHome 검사 위치)다. 중단 이유는 `KeyboardInterrupt`, 기록상 `held_slot=HBM-08`, `part_held_candidate=true`, 마지막 그리퍼 값18이다. 이는 실제 부품 보유 확인이 아니다. **사용자가 보고한 충돌의 정확한 순간·접촉 대상·원인은 미확정**이며 마지막 로그 위치를 충돌 위치로 단정하지 않는다. 상세 보고: `runtime/assembly_cycles/20260907-194725-908616/operator_collision_report.json`.

다음 작업은 현재 실제 부품 보유 상태, 접촉 대상 및 단계 확인을 먼저 하고 HBM-08 파지·리프트·TrayHome 복귀/검사 경로의 그리퍼 간섭을 점검한다. 원인 미해결 상태에서 기존 런처 재실행을 안내하거나 자동 복구/재파지하지 않는다. 관절 IK 통과는 실물 간섭 없음의 증거가 아니다. 오늘 마지막 요청에서는 기록만 했고 로봇·그리퍼·정지 해제·재개 명령을 보내지 않았다.


## Latest follow-up — camera Euler normalization, 2026-09-07

User run105917 captured board then failed TrayHome IK with C=-209.999858deg (controller112). Camera midpoints and all preflight IK inputs now normalize equivalent Euler values into[-180,180]; planning interpolation direction stays intact. Restarting at PlaceCamera near±180 no longer expands tiny feedback error into360deg. 142 tests passed. Current real start joints through PlaceCamera5 + TrayHome5 + saved non-SMD20 route432 + SMDView10 =452 linked IK waypoints passed without motion. Evidence `runtime/assembly_cycles/camera_angle_preflight_20260907.json`. Fresh full-cycle execution and SMD5 assembly remain unverified.

## Latest follow-up — immature detection anchor fix and PM03 transit, 2026-09-07

User run104454 failed before any pick: initial4–8 observations (<required20) were incorrectly used as VRM geometry anchors. Fixed warmup/quality-qualified anchors; pending geometry shifts restart that cell's collection, confirmed geometry changes remain gated. Actual capture-only now completed25/25. Additional dry preflight exposed PM02→PM03 J6 step182.714deg; added two safe-Z combined transit midpoints without changing endpoints or limits. 129 tests passed; actual non-SMD20 dry IK432 waypoints passed, max step94.950deg, J6[-173.768,177.772]. No robot/gripper motion sent during these fixes. Evidence: `runtime/assembly_cycles/tray_warmup_fix_20260907`. Fresh observations must be rechecked on the next execution; SMD and physical full-cycle completion remain unverified.

## Latest follow-up — bounded per-part recapture, 2026-09-07

The operator requested retries for failed detections. Tray capture now freezes each part after4 consecutive valid observations; initial15s +3 retry windows preserve accepted parts and resample pending ones. Physical cell matching, geometry/registration integrity and original timestamps remain gated. 124 tests passed. Live capture-only verified24 accepted while PM01 alone retried through4 attempts; PM01 still failed0.623<0.700, so no assembly started. Freshly verified stationary camera-only rejection no longer sends unnecessary StopMotion. Latest explicit ResetAllError had already cleared abnormal_stop; capture-only sent no motion commands. See today's PM01 comparison and `tray_retry_validation_20260907` evidence. PM01 shape is sound but model confidence lower than PM02–04; lighting/background/surface cause is not yet established.

## Latest follow-up — first launcher run and capture fix, 2026-09-07

User ran the launcher: board capture and TrayHome arrival completed; no part picked. Fixed duplicate-frame aging resetting the capture window; retained the 2s freshness gate for new frames. 106 tests passed and four live fresh detector outputs collected. Current separate blockers: PM01 confidence 0.687–0.699 below existing0.700 threshold; abnormal_stop=1 after timeout StopMotion. No error reset/re-execution performed. See today's log and `runtime/assembly_cycles/tray_capture_fix_20260907/fresh_frame_validation.json`.

## Latest session — one-command cycle launcher, 2026-09-07

Read [cycle launcher](FR5_CYCLE_LAUNCHER_KO.md) and [today's log](../작업일지/2026-09-07.md). `./run_fr5_cycle.sh --execute` now connects PlaceCamera capture, TrayHome capture, non-SMD20 with per-pick TrayHome removal inspection, then SMDView fresh capture and SMD5 assembly. No automatic recovery or historical SMD04/05 coordinate replay. New and existing regression tests: 103 passed. The launcher has NOT been physically executed. Latest update: operator requested gripper activation; ActGripper(1,1) returned0, activation query0,0,1 and valid feedback verified for >=1s. AUTO mode0; full launcher --check passed (TCP/teaching points/D435). No robot move or assembly execution. TCP [-2,-2,157,0,0,0] matched. Do not infer empty gripper from position0. Phone/board position changed slightly; phone registration restoration remains pending and is independent of the D435 assembly launcher.

## Latest session addition — phone inspection, 2026-09-06 evening

Read [phone-camera handoff](PHONE_CAMERA_HANDOFF_2026-09-06.md) and [today's final work log](../작업일지/2026-09-06.md) first for the next session. All 25 reference slots are displayed; actual part measurement currently covers SMD/CAP01–05 only. C03/04/05 display offsets were operator-confirmed. C03 placement/translation/rotation/removal checks passed in pixels. mm values are provisional; height correction is OFF and physical dimensions/intrinsics mapping remain unverified. Recurrent MOVED states remain unresolved; the final snapshot reports MOVED even though video continues. The phone work did not modify or execute robot placement recipes. The historical `camera2_droidcam/` entry below is not the active phone path; use `/home/juchan-yoon/.local/bin/fr5-phone-view`.

## Latest confirmed milestone — 2026-09-06

The operator confirmed one complete 25-part cycle succeeded, with minor shortcomings in board placement still remaining. GPU1/HBM8/PM4/VRM5/IND2/SMD5 are all completed. Read [the frozen success baseline](../vision_assembly/checkpoints/full_cycle_success_20260906/README.md) and [latest recovery history](RECOVERY_2026-09-06.md) before relying on older status/vision descriptions below.

The baseline includes actual per-slot executed criteria, recipes, Tool1 TCP, camera parameters, calibration, weights, recovery scripts, and operator-clicked SMD04/05 terminal coordinates. Recovery and operator assistance were part of this cycle; this does not establish an unattended uninterrupted run or perfect placement accuracy. Preserve the existing numerical settings until a specific refinement is measured.


## Instruction to the next Codex

Read this entire file before changing or running the project. Then read
`PROJECT_GOAL.md`, followed by the subsystem document relevant to the requested
task. Do not infer that a successful ROS build authorizes physical robot or
conveyor motion.

## System objective

Build an automated cell that stops a TurtleBot-driven conveyor when a package
board reaches the assembly station, estimates board/part pose with vision,
uses the FR5 to pick and place package-model components, inspects the assembly,
and reports PASS/FAIL. Current work is an incremental prototype, not a finished
production safety system.

## Repository map

- `robot_ws/`: isolated FAIRINO ROS 2 command server workspace.
- `calibration/`: D435 ChArUco intrinsics, Eye-in-Hand calibration, part
  detection and guarded FR5 motion scripts.
- `vision_assembly/`: board detection, slot recipes and pick-to-board hover.
- `ros2_ws/`: ROS interfaces, AI/Vision server and TurtleBot conveyor stop
  controller.
- `camera2_droidcam/`: S22 DroidCam USB bridge.
- `gopro_camera3/`: optional cell-monitoring camera.
- `docs/logs/`: subsystem work history and portfolio/presentation evidence.

## Hardware and ROS assumptions

- Ubuntu 24.04, ROS 2 Jazzy, default `ROS_DOMAIN_ID=5`.
- FAIRINO FR5 controller web address used in this cell: `192.168.58.2`.
- TurtleBot used for conveyor prototype: `192.168.0.101`, model `burger`.
- D435 ROS namespace: `/camera/camera/...`.
- FR5 state: `/nonrt_state_data`; command service:
  `/fairino_remote_command_service`.
- TurtleBot `/cmd_vel` type on the tested Jazzy machine is
  `geometry_msgs/msg/TwistStamped`.
- Device-specific values belong in ignored `config/ksmc.env`; start from
  `config/ksmc.env.example`.

## Critical robot facts that must not be overwritten

- The physical TCP was calibrated on the FR5 controller as `toolcoord1`.
- The latest manually edited controller TCP was approximately
  `X=-2 mm, Y=-2 mm, Z=157 mm`; verify the controller before motion because
  earlier records also mention approximately 165 mm.
- Do not add TCP length into the Hand-Eye transform. FR5 `MoveCart` uses the
  active controller tool coordinate.
- D435 is Eye-in-Hand and fixed to the gripper bracket. If camera/bracket/tool
  mounting changes, existing Hand-Eye calibration is invalid.
- `calibration/data/handeye_result.json` is tied to the tested physical
  robot-camera mounting. Its own warning and validation fields must be read.
- Never copy calibration blindly to a different FR5/D435 mounting. Recalibrate.

## Current vision method

Small-part picking currently uses ChArUco as a board coordinate reference,
not YOLO. The color image is rectified with observed ChArUco corners; black
cells are searched using brightness, HSV profile, expected area and contours.
`minAreaRect` supplies center and long-axis direction. ChArUco pose + saved
Eye-in-Hand transform + current flange pose convert the part into FR5 Base.
Depth is subscribed as a supporting height measurement, but tested picks may
fall back to RGB board plane plus configured part height.

## Current tested conveyor behavior

`run_s22_conveyor.sh` publishes the S22 image and stop-line detection.
`run_conveyor_auto_stop.sh` commands TurtleBot at 0.10 m/s until the board
trailing edge crosses the line. Vision heartbeat loss and Ctrl+C publish zero
speed. This is a prototype auxiliary control, not a certified safety function.

## Setup on a new computer

1. Clone the repository, preferably as `$HOME/KSMC`.
2. Copy `config/ksmc.env.example` to ignored `config/ksmc.env`; set S22 serial
   and any changed domain/device values.
3. Run `scripts/setup_new_computer.sh`. It installs project dependencies,
   fetches the pinned FAIRINO source and builds both ROS workspaces.
4. Run `scripts/doctor.sh` and resolve every `FAIL` before hardware execution.
5. Connect devices and verify topics read-only before starting command nodes.

If FAIRINO upstream layout or its pinned commit fails, inspect
`robot_ws/README.md` and `robot_ws/setup_fairino_vendor.sh`; do not silently use
an arbitrary new commit.

## Safe startup order

Assembly-cell update (2026-09-06): use `./run_fr5_assembly_stack.sh preflight`,
then `start` and `check`; use `view` from a desktop terminal for RQT. See
`docs/FR5_ASSEMBLY_STACK_COMMANDS.md`. The individual steps below are for isolated
subsystem diagnosis; do not start a second FAIRINO driver alongside the stack.
Read the final section of `작업일지/2026-09-05.md` for the latest physical handoff.
GPU1/HBM8/PM4/VRM2 completed commanded placement sequences, but PM03/04 center
errors and the opposite VRM placement branch were reported. VRM03 stopped with
possible part retention, unconfirmed physically, and abnormal_stop=1. Do not
resume a historical plan or treat last_verified_tcp as the current pose.
VRM C180 placement branch locking and executor rejection are now implemented
and covered by 45 related tests (September 6); fresh captures, live IK and
physical placement validation remain pending. PM03/04 correction validation is pending.
The subsequent September 6 VRM fix does not resume motion. The user confirmed
an empty gripper and VRM03 present in the tray; latest observed mode is manual. Keep Real Backend hardware execution disabled. Recheck historical
running-state claims and obtain fresh board/tray observations before planning.

1. D435 only: launch RealSense, inspect RGB/depth topics.
2. FR5 only: run `robot_ws/run_command_server.sh`, echo one state sample.
3. Detection only: run ChArUco/part detection in dry-run.
4. Motion: only after checking active tool, AUTO mode, emergency state,
   calibration file, target freshness and dry-run target.

For S22 conveyor testing, start TurtleBot bringup and S22 detection first, then
use the explicitly confirmed conveyor script. Never run multiple `/cmd_vel`
publishers simultaneously.

## Verification commands

```bash
./scripts/doctor.sh
./scripts/build_all.sh
source scripts/ksmc_env.sh
python3 -m pytest ros2_ws/src/vision_server/test -q
```

Read-only hardware checks:

```bash
ros2 topic echo /nonrt_state_data --once
ros2 topic list -t | grep -E 'camera|cmd_vel|odom|nonrt_state'
ros2 topic info /cmd_vel -v
```

## Documents by task

- Overall requirements: `PROJECT_GOAL.md`
- FR5/Hand-Eye: `calibration/COORDINATE_DIAGNOSTIC.md`,
  `calibration/RUN_COMMANDS.md`, `docs/logs/robot.md`, `docs/logs/vision.md`
- Board assembly: `vision_assembly/README.md`
- AI/Vision package: `ros2_ws/src/vision_server/README.md`
- Conveyor: `docs/CONVEYOR_VISION_ROS_ARCHITECTURE.md`,
  `docs/logs/system_integration.md`
- S22: `camera2_droidcam/README.md`
- Architecture: `docs/architecture/TEAM_SYSTEM_ARCHITECTURE.md`

## Git hygiene

Do commit source, configuration templates, active calibration files, test data
needed to reproduce results, and docs. Do not commit `build/`, `install/`,
`log/`, `runtime/`, `config/ksmc.env`, passwords, tokens or private keys.
Before pushing, inspect `git diff --cached` and search for secrets and absolute
home paths.

## Known incomplete areas

- Final table/conveyor belt and fixed S22 installation are not complete.
- S22 hand-to-eye calibration is not complete.
- Final board slot coordinates require re-registration after mechanical setup.
- YOLO training weights/dataset are not final.
- GoPro safety-zone detection is optional and must not replace physical safety.
- Full automatic placement and final PASS/FAIL inspection are not finished.


## 2026-09-07 PM03/04 실제 배치 실패 및 PM04 접촉 보고

- 실행 `20260907-110419-530107`: GPU/HBM/PM 13개는 동작 기록만 완료. 사용자가 PM03·04 위치 불일치 및 PM04가 옆 노란색 홀 부근에 걸리며 하강했다고 보고했다. 이 슬롯들은 실제 안착 성공이 아니다.
- VRM01은 TrayHome에서 기존 셀 점유가 남아 배치 전에 중단했다. 보유 후보 필드는 실제 파지 증거가 아니며, 빈 그리퍼 여부는 사용자 확인 대기다.
- PM03/04 중심 오차는 `docs/RECOVERY_2026-09-06.md`에도 미해결로 남아 있다. 25개 동작 완료를 배치 정확도 검증 완료로 취급하면 안 된다.
- 두 슬롯 보정은 보드 좌표계 `[+0.002,+3.999]mm`; 원인으로 확정하거나 임의 제거하지 않았다. 실제 잡힌 중심/방향과 목적지 보정의 정합성을 확인해야 한다.
- 접촉 후 보드 위치/부품 상태 미확인. 정지 해제 및 전체 재실행하지 않음. 이번 조사에서는 로봇 명령과 보정 변경 없음.
- 근거: `runtime/assembly_cycles/20260907-110419-530107/operator_physical_failure.json`. 다음 단계는 그리퍼 보유 상태 확인 및 PM04 접촉 위치 확인 후 재측정/개별 검증이다.


## 사용자 요청 PlaceCamera 현장 확인

- 사용자가 현재 놓인 위치를 목표로 확인하라고 지시하여 PlaceCamera 이동/촬영 완료. 증거 `runtime/assembly_cycles/pm34_inspection_20260907/`.
- TrayHome 현재 상태에서 abnormal_stop=1만 활성, AUTO/정지/Tool1/User0 확인 후 기존 검사 실패 StopMotion latch를 ResetAllError()로 해제했다. 직후 검증 스크립트는 남은 이전 상태 메시지로 실패했으나 후속 camera_stage의 새 상태 안전 검사는 통과했다.
- 기존 camera_stage 전체 5경유점 IK 통과, maxstep33.808도. Z350 경유 후 PlaceCamera Z321.342 도착 및 새 board 촬영 완료. 그리퍼 명령/조립 하강 없음.
- 영상 기준 PM03=위쪽 수평 노란 부품, PM04=아래쪽 수평 노란 부품. 현재 보이는 위치를 사용자 의도 목표의 참고 영상으로 보존했다.
- 단일 영상 색상 외곽 중심: PM03 pixel[738.96,324.97], PM04[739,564]. 네 홀 평면 호모그래피로 추정한 기존 슬롯 대비 보드XY차이 각각[+3.290,-0.260], [+3.001,-0.883]mm. 부품 높이 시차 미보정 진단값이며 실행용 보정으로 적용하지 않았다. `visible_pm_centers.json` robot_motion_authorized=false.
- 새 보드 슬롯 surface Base는 실행 전 대비 PM03[-7.178,+0.828,-0.174], PM04[-6.460,+0.831,+0.009]mm 변화. 실제 보드 이동과 추정 오차 기여를 분리하지 못했으므로 접촉 원인 확정 불가, 이전 촬영 좌표 재사용 금지.
- 로봇은 PlaceCamera에 정지. VRM01 보유 여부 확인은 여전히 미완료.


## PM03/04 재배치 시험 준비 (사용자 현장 준비 완료 대기)

- 사용자가 기판을 비우고 부품을 다시 놓아 PM03/04 시험을 요청했다. 빈 그리퍼/트레이 재배치 완료 및 기판 이동 여부를 비동기로 질문했으며 아직 답변 없음. 이번 준비 단계 로봇 명령 없음.
- `execute_full_fixed_cycle.py --stop-before-place`: 단일 새 파지에 한해 최종 배치 높이+50mm에서 보유 상태로 정지, 최종 하강/해제/후퇴 없음. 기록 status=`paused_before_place_visual_confirmation_required`; 기존 resume-held로 재개 가능한 상태가 아님.
- `build_pm_placement_review.py`: 새 snapshot과 `visible_pm_centers.json`으로 단품 상공 검증 전용 후보를 계산. 기존 슬롯 정적 보정 대신 관측 중심 이동+신규 파지 보정을 회전시킨 임시 보유 오프셋을 적용, 미세 회전 생략 기준은 테스트 내부에서0. 공유 레시피/슬롯 설정 변경 없음.
- 이미지 높이 시차 및 검출 편향/실제 보유 오프셋 분리는 미검증. 생성 plan은 execution_scope=`placement_review_hover_only`; stop-before-place 없이는 execute()가 ROS 접속 전 거부한다. 후보로 최종 하강 금지. 상공에서 중심 검증 후 별도 검증한 최종 배치 절차 필요.
- `pm03_offline_review_example.json`, `pm04_offline_review_example.json`은 과거 snapshot으로 계산한 오프라인 예시만. 재촬영 전 실행 금지. 실제 경로 IK는 현장 준비 및 새 캡처 뒤 수행한다.
- 시험 순서: 현장 준비 완료 → 현재 PlaceCamera 새 board 촬영 → TrayHome 안전 이동/새 tray 촬영 및 실제 셀 번호 확인 → PM03 검증 전용 계획/IK/파지 후 TrayHome 검사/배치 상공 확인 → 검증된 개별 배치 → PM04 같은 순서. 전체25 런처 재시작 금지.


## PM03 상공 시험 실제 실행 완료 — 정렬 확인 대기

- 사용자 준비 완료 후 PlaceCamera에서 빈 기판 새 촬영, TrayHome 이동 완료. 디렉터리 `runtime/assembly_cycles/pm34_test_20260907/`.
- 전체25 촬영은 PM 신뢰도/VRM geometry 변동 및 SMD 품질 미달로 완료하지 못했다. 이후 PM 구역 네 셀만 원래 레시피 품질 기준(관측20, 신뢰도0.7 등) 및 4개 연속 최신 프레임/XYZ2mm/각도3도/셀12px/동일 handeye/현재 정상 TrayHome 상태를 검사해 `pm_snapshot.json` 생성. 다른 구역 품질은 이번 PM 시험 범위에서 제외; PM 품질 기준 완화 없음.
- `pm03_review_plan.json`: 최신 보드 기준 후보 최종TCP [35.234870,-562.096859,87.927...,180,0,91.276...]. 정확한 전체 값은 계획 JSON 참고. 기존 슬롯 보정 대비 XY 약[-4.065,-3.573]mm. 이 후보는 상공 검증 전용이며 최종 배치 확정값이 아님.
- 단품 형식은 `--selected-slots PM-03` (explicit_slots 계획에 --only-slot을 쓰면 검증 거부). dry-run 23경유점/maxstep41.234도/J6[-4.689,82.078] 통과.
- `--verify-tray-pick --stop-before-place --execute --confirm-cycle`로 실제 PM03 집기/그리퍼25/100mm리프트/TrayHome 셀 제거 검사 통과/기판 상공 이동 완료. 검사는 셀 제거 증거이며 실제 파지 외관을 독립적으로 증명하지는 않는다.
- 현재 status=`paused_before_place_visual_confirmation_required`, PM03 보유 후보, 그리퍼25, 최종 하강/해제/안착 없음. PM04 아직 집지 않음. PM03 현재 실제 중심 정렬 확인 후 다음 진행 필요. 기존 전체 런처/다시 집기/기존 resume-held 실행 금지.

- 사용자 “좀 더 내려가야 알 것 같다” 요청으로 PM03을 기존 상공50mm에서 10mm씩3회 저속 하강, 최종 배치 높이+20mm(TCP Z107.926936)에서 정지. 3경유점 IK/maxstep1.453도 통과, SetSpeed20/MoveL10. 그리퍼25 유지, 해제 없음. 최신 상태 기록은 `runtime/assembly_cycles/pm34_test_20260907/pm03_hover20_run.json`이며 이전50mm 정지 기록으로 재개하면 안 됨. 중심 확인 대기.

- 사용자의 “파지까지 가봐”를 현재 보유 중인 PM03 배치 높이까지 하강 요청으로 해석한다고 알린 뒤, +20mm에서 +15/+10/+5/+2/+0mm 5경유점 저속 하강 완료(SetSpeed10/MoveL10). 최종 목표 TCP[35.234870,-562.096859,87.926936,180,0,91.276]. 그리퍼25 유지, 해제 없음. 최신 기록 `runtime/assembly_cycles/pm34_test_20260907/pm03_at_placement_height_run.json`, status=paused_at_placement_height_gripper_closed. 실제 안착/접촉 외관 사용자 확인 대기. 이전 상공 기록으로 재시작 금지.


## PM03 정렬 확인/해제 완료, PM04 +20mm 정지

- 사용자 PM03 “딱 맞는다 지금” 확인을 `pm03_release_run.json`에 기록. 그리퍼30 해제 피드백 후 수직100mm 후퇴 완료. PM03은 사용자 정렬 확인을 받았으나 전체 레시피/슬롯 설정에는 아직 반영하지 않음. PlaceCamera 새 영상 `pm04/board.jpg`에서 상단 PM03이 놓여 있음 확인.
- PM04 새 기판 촬영과 TrayHome 이동 후 남은 PM01/02/04를 이전 reference pixel12px 이내로 대응, 원래 품질 기준 및 4프레임 안정 검사 완료. 실행 스크립트/관측은 `runtime/assembly_cycles/pm34_test_20260907/pm04/` 보존.
- PM04 후보 최종TCP [33.594745736,-474.895346159,89.751326,-180,0,91.215909223]. PM03과 같은 테스트 보정 방식, 최종 정렬은 아직 미확인. 22경유점/maxstep41.265도/J6[-8.130,80.693] 검사 통과. 파지25/100mm리프트/TrayHome 원래 셀 제거 확인/목표+50mm 정지 완료.
- 이전 50mm에서 판단이 어려웠다는 사용자 피드백을 적용해 PM04도 추가30mm를10mm씩 저속 하강, 현재 최종 배치 높이+20mm(TCP Z109.751326)에 그리퍼25로 정지. 최종 하강/해제 없음. 최신 기록 `pm04/pm04_hover20_run.json`, status=paused_20mm_above_placement.
- PM03 기판에 배치, PM04 보유 후보 상태이므로 전체런처/재파지 금지. PM04 현재 정렬 확인 뒤 개별 진행. 과거 PM03 상공/보유 기록으로 재개 금지.

- 사용자 PM04 “파지까지 가” 요청에 따라 배치 높이까지 +15/+10/+5/+2/+0mm 5경유점 저속 하강 완료(SetSpeed10/MoveL10, maxstep0.831도). 최종 목표TCP[33.594745736,-474.895346159,89.751326,-180,0,91.215909223], 그리퍼25 유지, 해제 없음. 최신 기록 `runtime/assembly_cycles/pm34_test_20260907/pm04/pm04_at_placement_height_run.json`, status=paused_at_placement_height_gripper_closed. PM04 정렬 사용자 확인 대기, 이전 상공 기록으로 재개 금지.

- PM04 사용자 “어 맞아” 확인 후 그리퍼30 해제/100mm 수직후퇴 완료. `pm04/pm04_release_run.json`. PM03/04 두 정렬 확인 및 해제 기록은 `runtime/assembly_cycles/pm34_test_20260907/validated_pm34_result.json`. PlaceCamera 최종촬영 `final/board.jpg`에서 두 부품이 놓여 있음 확인. 현재 PlaceCamera 정지/그리퍼30, 두 부품 보유 해제. 공유 런처 설정에는 아직 테스트 보정 미반영. 사용자는 다음으로 VRM 파지 실패 원인 분석 요청.

- VRM01 실패 분석: 인식 신뢰도0.952/관측23으로 검출 품질 통과, open28/close24 피드백 정상. TrayHome 셀 점유로 실패. 고정TCP Z-53.238을 사용해 기준 표면Z-45.306 대비7.932mm 하강이던 조건이 당시 표면Z-46.308 대비6.930mm로 약1mm 얕아짐. 높이 조건은 원인 후보이며 확정 아님. 도착 로그 Z-52.775(목표보다0.463mm 위)는 그리퍼 접촉 순간 값인지 알 수 없음. 그리퍼전류가 전 슬롯0이므로 VRM 단독 실패 증거로 사용 불가. `vrm01_failure_diagnosis.json` 보존, 진단 중 로봇 이동/설정 변경 없음.


## VRM01 기존 조건 5mm 시험 리프트 완료

- 사용자 “해봐” 요청으로 PlaceCamera→TrayHome 이동, VRM5개 새 촬영/관측20/원래 품질 기준/4프레임 안정성 통과. `runtime/assembly_cycles/vrm01_pick_test_20260907/`에 실행 스크립트와 증거 보존.
- 새VRM01 검출[-746.208,-219.847,-46.308], 축1.587도. 기존 조건 그대로 pick[-747.700,-219.757,-53.238,-180,0,87.087], open28/close24. 높이·보정 변경 없이 원인 분리 목적.
- 6경유점 IK/maxstep62.325도/J6[-4.689,11.674] 통과 후 파지 및 수직5mm 리프트 완료. 사용자 파지 외관 확인 대기. 기판 이동/해제 없음.
- 도착 로그는 Z-52.759였지만, 추가1초 정지 후 닫기 직전 실제 Z-53.258, 닫은 뒤Z-53.247로 목표에 도달한 것을 기록했다. 따라서 도착 로그 약0.5mm 차이만으로 실제 닫기 높이가 높았다고 판단하면 안 됨. 이번 추가 정지 기록만으로 과거 실패 원인을 확정할 수 없음.
- 현재 `short_lift_run.json` status=paused_after_5mm_lift_visual_confirmation_required, VRM01 보유 후보/그리퍼24, 목표 TCP[-747.700,-219.757,-48.238,-180,0,87.087]. 실제 부품이 들렸는지 사용자 확인 뒤 다음 단계 진행. 절대 재파지/기판 배치/더 낮추기 자동 실행 금지. PM03/04는 이미 기판에 놓여 있음.

- 사용자 “미세각도 못잡고 그냥 내려간 것 같다” 확인 요청. 이번 검출 Base축1.587도, tool_y 정렬 기본C91.587도에서 기존 VRM 고정보정-4.5도를 적용한 명령C87.087도, 닫기 직전실제C87.087212도/닫은뒤87.087425도. 회전 명령 생략 또는 실행 누락 근거는 없음. 단, 고정보정이 현재 실제 축에 맞는지 미확인. YOLO polygon이 상류에서 정수 반올림된 뒤 minAreaRect에 쓰이며, 관측20프레임 자체가 각도 정확도 검증은 아님. 진단 중 로봇 이동/회전/설정변경 없음; 5mm리프트 보유 상태 확인 대기 유지.


## VRM01 사용자 각도 불일치 접촉 보고 — 시험 실패

- 사용자가 “각도가 달라서 부딪혔어 부품이랑”이라고 명확히 보고했다. 이번5mm리프트 시험을 파지 성공으로 간주하지 않는다. 원인 우선순위는 실제 부품 축과 그리퍼 축 불일치이며 높이 가설만으로 진행하면 안 된다.
- 명령C87.087과 실제C가 일치한 것은 기계적 정렬 정확도의 증거가 아니다. 검출 축, tool_y 변환, 과거 -4.5도 보정, 영상상의 실제 부품 축을 대조해야 한다. -4.5도만 원인으로 확정하거나 임의 제거하지 않음.
- 진단시 부품을 치웠거나 비었다고 확인받지 않은 상태로 회전/더깊은하강/재파지 금지. 기존 short_lift_run 보유후보는 실제파지 확인이 아니다. 최신 현장 상태/접촉 보고는 `runtime/assembly_cycles/vrm01_pick_test_20260907/operator_angle_contact.json`. 현재 정지 확인 외 이동/그리퍼 명령 없음.

- 사용자 부품이 트레이에 남았다고 확인. 그리퍼28 열기/수직안전Z350 후퇴/TrayHome 경유복귀 완료, 최신 empty_retreat_run.json status=empty_gripper_at_trayhome. VRM파지 실패확정, 빈그리퍼28. 새 after_retreat.jpg 저장.
- 접촉 전 원영상 VRM01 양쪽 긴모서리의 수평그래디언트 subpixel 피팅 진단: 중심±9px 구간 영상각85.859/86.143도, 기존 검출89.34도와 약3.34도 차이. 접촉후85.474/85.431도. 단일이미지/고정ROI 진단으로 실행각 확정하지 않음. 변환 비교는 edge_angle_diagnostic.json comparison 참조. 검출각 편향과 과거-4.5도 고정 보정 양쪽을 분리 검증해야 함. 설정/보정 수정 및 재파지 없음. 현재 TrayHome 정지.


## VRM01 실제 모서리 각도 재시험 — 5mm 리프트 후 확인 대기

- 사용자 “아니 해봐 일단” 요청으로 새 RGB12프레임/양쪽 모서리 subpixel 피팅/좌우각차1.5도 이내/잔차0.2px 미만/각도span1도 미만/현재 정상 TrayHome/VRM검출 원래 품질 기준을 검사했다. 실제12프레임 영상각85.441726도, Base축5.483058도, span0.442672도. `capture_edge_retry.py`, `edge_retry_angles.json`, `edge_retry_snapshot.json`, `edge_retry.jpg` 보존.
- 단품 시험에만 기존 pick_axis_offset -4.5도를0으로 설정하고 새모서리축을 사용. pickC95.483058도, XYZ[-747.536,-220.006,-53.238], open28/close24. 공유 설정파일 변경 없음. 새표면Z-45.814로 이전 관측과0.494mm 차이가 있어 각도 외 조건이 완전히 동일하다고 주장하면 안 됨.
- `pick_edge_retry.py` dryrun11경유점 maxstep62.404/J6[-4.689,3.274]통과 후 --execute. SetSpeed10, 마지막50mm분할하강, 닫기직전1초 정지 기록. 실제닫기직전C95.484/Z-53.244. 닫기24 후5mm 수직리프트 완료.
- 현재 최신기록 `runtime/assembly_cycles/vrm01_pick_test_20260907/edge_retry_run.json`: status=paused_after_5mm_lift_visual_confirmation_required, VRM01보유후보/그리퍼24, 목표TCP[-747.536,-220.006,-48.238,-180,0,95.483058]. 실제파지/접촉여부 사용자확인 대기. 기판이동/해제 없음. 이전실패 angle87.087/빈그리퍼후퇴 기록으로 재개 금지.

- 사용자 새 각도는 맞지만 그리퍼가 들어갈 때 이상하다고 보고, 그리퍼값 의심. 새C95.483의 실제정렬은 사용자 확인을 받음. 현재 실제파지 여부는 미확인. 적용값은 하강전open28/닫기24(피드백 일치), executor _gripper_positions는 VRM horizontal레시피를 사용. vertical grip32/release34 설정도 있지만 현재 tool_y축 정렬 파지에 그대로 대체할 근거는 없음. 하강중 접촉 후보는 열림폭 부족 또는 중심 편차; 닫힘24만으로 원인 설명불가. 진단중 로봇/그리퍼 조작 없음, 재시도 전 보유상태 확인 필요.


## VRM01 재시험 접촉/주변 부품 이동 보고 및 내려놓기 완료

- 사용자 “부품 내려놓고 다시해야 돼, 들어갈 때 찍어서 옆 부품이 흐트러졌다” 보고. 새 각도 정렬 확인과 별개로 진입 접촉이 있었고 주변 재고 좌표가 무효다. 재시험을 정상 파지 성공으로 표시하면 안 됨.
- 사용자 명시 요청으로 현재XY/ABC를 유지한 수직5mm하강 → gripper28해제 피드백 → 수직100mm후퇴 완료. 최신 `runtime/assembly_cycles/vrm01_pick_test_20260907/operator_requested_putback.json`, status=released_and_vertically_retracted, part_held_candidate=false. 현재 TCP 약[-747.535,-220.008,46.762,180,0,95.483], gripper28.
- 주변 부품 재정리 완료 대기. 기존 vrm/edge snapshots 재사용 금지. 재정리 뒤 새촬영/실제 중심 및 양쪽 진입 여유 확인 필요. 열림28부족은 가설이며, 더 넓히면 주변부품 간섭이 늘 수도 있어 무조건30으로 내리지 말 것. 새로운 각도 방식도 현장접촉 없는 파지로 검증된 상태는 아님. 이번 내려놓기 이후 이동/재파지 명령 없음.


## VRM01 재정리 후 새촬영/진입 전20mm 정지

- 사용자 “다시 해봐” 요청 후 TrayHome 복귀. 트레이검출 프로세스 정지 및 깊이 스트림 단절을 발견했다. RGB는 약77/6초 수신했지만 depth0, 카메라 Frame Corrupted 반복. 트레이비전만 기존설정 재시작(pid1579431), 카메라만 원래1280x720x15/depthsync/initial_reset 설정 재시작(pid1651793). 관리pid파일 갱신, 로봇드라이버 재시작 없음. 이후 검출age1.31초 및 새12프레임 확보. USB불완전프레임 경고 원인 자체는 미확정/완치주장 금지.
- `retry2_capture.py`: 재정리된 VRM01 새 중심/모서리12프레임 측정. 영상각90.408527도, Base축0.519148도, span0.437294도. `retry2/edge_retry_snapshot.json`, `edge_retry_angles.json`, `edge_retry.jpg` 보존. 새 pickXYZ[-745.620,-218.784,-53.238], C90.519148. 이전 손상/재정리전 좌표 사용하지 않음.
- 실제 그리퍼 틈과28/30의mm 대응은 미검증. 주변 간섭을 피하려고 무조건 더열고 파지하지 않고, 열림28로 진입 전+20mm까지만 접근. `retry2_approach.py`: 5경유점/maxstep60.922/J6[-4.689,8.183]검사후 SetSpeed10 이동. 닫기/파지/접촉하강 없음.
- 현재 최신 `runtime/assembly_cycles/vrm01_pick_test_20260907/retry2/approach_run.json`: status=paused_before_pick_20mm_open_gripper, held=false, gripper28, 목표TCP[-745.620,-218.784,-33.238,-180,0,90.519148]. 실제양쪽진입여유/중심을 사용자와 확인한 뒤 다음단계 진행. 이전보유기록으로재개 금지. PM03/04는 기판에 놓여 있음. 계획 pick_item의 placeTCP는 과거board기준이며 이번사용범위에포함안됨/배치금지.

- 사용자 “파지까지 가봐” 요청으로 retry2의 파지높이까지+15/+10/+5/+2/+0mm 저속분할하강 완료(SetSpeed10/MoveL10, maxstep0.491도). 현재 목표TCP[-745.620,-218.784,-53.238,-180,0,90.519148], gripper28열림 유지/닫기없음/held=false. 최신 `runtime/assembly_cycles/vrm01_pick_test_20260907/retry2/at_pick_height_open_run.json`, status=paused_at_pick_height_gripper_open. 그리퍼 진입 접촉/중심/폭에 대한 사용자 확인 대기. 도착로그Z-52.772는 정착전 허용오차내 값일수있음; 실제안착/접촉성공 주장금지. 이전20mm상공/보유기록으로재개 금지.

- 사용자 “누른다” 보고: retry2 그리퍼28열림 상태로 기존파지Z-53.238까지 접근했을 때 압박 접촉 발생. 닫기24는 아직 실행하지 않았으므로 닫힘동작이 원인은 아님. 현재XY/ABC/열림28 유지한 수직5mm+추가15mm 후퇴 완료. 최신 `runtime/assembly_cycles/vrm01_pick_test_20260907/retry2/pressure_relief_run.json` status=vertically_retracted_20mm_gripper_open, 실제목표Z약-33.244. 기존20mm접근/접촉높이 기록으로 재개 금지. 손끝이 부품윗면에 걸린 것인지, 진입 후 과하강/본체접촉인지 미확인. 압박 원인 확인 전 추가하강/닫기 금지.

- 사용자 이전수정성공을 지적하며 “카메라기준 부품 오른쪽 윗면에 닿아” 보고. 9/4작업일지의 기존중심[-1.492,+0.090]/C85.677/열림28/닫힘24/Z-53.238 성공기록 확인, 이번에도 중심보정은 적용됐으므로 누락이라 말하면 안 됨. 각도변경에 따른 고정보정회전차이 및 영상모서리 중심비교는 retry2/right_top_contact_diagnosis.json. 이전보정을 통째로회전하는 것만으로 해결된다고 주장하면 안 됨. 카메라왼쪽 방향을 당시 T_base_camera에서 계산해 기록. 현재20mm상공 열림28 정지 유지, 재하강/조임/좌표수정 없음.

## VRM02–05 공통보정 파지 시험 완료
- 사용자 “오케이 다 잘들어가서 집었다”로 2/3/4/5 모두 진입/실제파지 성공 확인. 각 부품 새12프레임 네모서리중심/긴모서리각도 측정, Base보정[-1.516428864,+1.589801064], 진입30/파지24/5mm리프트/원위치28해제 후 TrayHome 복귀 완료. 통합기록 runtime/assembly_cycles/vrm01_pick_test_20260907/vrm2345_140145/validated_result.json 및 각 operator_result.json.
- 현재 최종로봇상태 vrm05/home_run.json: TrayHome/빈그리퍼28, 모든시험부품 트레이해제 완료. PM03/04만 기판에 있음. 공유레시피 중심보정/그리퍼값 저장 및 성공출처 갱신. 단 공유런처는 기존검출각-4.5 경로가 남아 있고 시험은 새네모서리중심/모서리각도0보정 사용. 전체런처에 새영상계산 통합 완료 아님; 기존런처 재실행을 이번시험과 동일하다고 말하지 말 것. 기판배치28은 이번트레이원위치해제와 별개로 미시험.

## SMD01 파지 시험 — 실제 보유 확인 대기
- 사용자 “혹시 모르니까 smd도 잡으러 가봐” 요청. 빈TrayHome28에서 SMDView로 이동, 근접원본24프레임 측정. smd_pick_test_20260907_141323/smd_close.json 단품1 통과. 전체촬영 smd_all.json은3번 실패, 재촬영 smd_all_retry.json은2/3번 실패(중심span 등), 기준완화 없음. 실제실행은 독립통과한1번만.
- SMD01 재촬영 center[-624.686,-166.282,-47.291], axis-5.649도, 기존Base보정[-2.089,+2.779], ToolX음수분기, 고정Z-52.177 사용. pick01.py는 보드배치 없는15경유점 단품경로, preflight통과/J6최대101.443도. 열림18/닫기12 후5mm수직리프트 완료.
- 현재 최신 runtime/assembly_cycles/smd_pick_test_20260907_141323/pick01_run.json status=paused_after_5mm_lift_visual_confirmation_required, held_candidate=true/gripper12, 실제TCP[-626.785522,-163.504013,-47.162960,179.999527,0.001236,-5.648931]. 실제진입/보유 사용자 확인 대기. 해제/기판배치/다른SMD파지 없음. 이전VRM빈그리퍼 상태로재개 금지.

## PM03/04 배치 및 VRM 파지의 단일 런처 통합 완료

- 사용자 요청으로 full_cycle_plan에 PM03/04 검증된 보드 중심 이동+carried pick correction 적용. 예전 슬롯보정 제거, 새보드변환/새파지각도로 계산, 작은회전생략0. 당시 두 성공목표를1e-6 허용오차로 재현. PM01/02 유지.
- vrm_edge_refinement.py 및 capture_vrm_refinement.py 추가. 사용자확인2~5시험의 네모서리중심/모서리각도 계산을 TrayHome에서 새12프레임씩 수집. 부품별검증/120초제한/기하변화거부/셀번호보존, 다섯개통과후원자적snapshot갱신. 새angle_source=vrm_four_edge_v1에는 기존-4.5 미적용. 중심Base[-1.516428864,+1.589801064] 1회적용, 열림30/파지24/해제28.
- assembly_cycle_launcher.py에 capture_tray→refine_vrm→plan_non-smd 연결, 총13단계. 기존 일반매파지TrayHome검사 유지. assembly_launcher_revision.json에 검토된레시피해시 보존, 나머지설정은9/6동결본일치 유지. 동결본수정없음. 실행중설정변경거부 유지/강화.
- ROS 환경 관련127테스트 통과, run_fr5_cycle.sh --dry-run 통과, 새스크립트구문검사 통과. 실제전체런처/카메라재촬영/로봇조작은 이번코드통합중 수행하지 않음. 현재물리상태 여전히 SMD01을gripper12로5mm들고정지(사용자보유확인), PM03/04기판에있음. 전체재시작은 빈그리퍼/빈기판/25개재준비 필요. 이전 인계의 “VRM 새영상 계산 런처미통합”은 이번수정으로 해소됨. SMD 품질기준/촬영방식은 변경하지 않음.

- 사용자 “놓고 트레이홈으로 돌아가, 런처 명령어” 요청으로 SMD01 현재XY/각도 유지5mm하강→17해제→수직350후퇴→TrayHome복귀 완료. 최신 runtime/assembly_cycles/smd_pick_test_20260907_141323/putback_home_run.json status=at_trayhome_empty_open17, held=false, 실제TCP[-527.990662,-60.956028,337.860291,179.997391,0.000213,89.999565]. 이전SMD보유기록은해제됨. 전체런처는 실행하지 않음. 명령 ./run_fr5_cycle.sh --execute; 새사이클은 빈기판/트레이25개준비 후 시작.

## 14:38 런처 capture_tray 실패 진단 및 수정
- 실패run20260907-143803-398051: PM02/03 및SMD1~5 낮은신뢰도로60초재시도소진. 새사진 failure_inspection.jpg 확인: 부품존재/큰가림없음. PM 중복후보가비율우선으로저신뢰도후보를선택하는문제 발견. 같은사진640에서PM02 .716/.210중복,960에서는네개고신뢰도후보 .97/.96/.865/.783.
- pm_mask_selection.py추가: 기존품질기준모두통과한후보우선, 이후기존비율/점수순서. detect_tray_parts.py에PM전용960추론 추가(카메라1280유지/타부품640). 기존너무넓은mask거부/중복억제/품질검사유지.
- 런처TrayHome에SMD근접검증지연옵션추가. SMD20관측/개수/셀식별/형상은유지,먼거리confidence판정만SMDView로넘김. snapshot deferred_to_smd_close=true, full_cycle_plan에서해당SMD픽거부. 검증된근접측정merge후만false. 기본직접촬영은기존엄격기준유지. 품질설정임계값변경없음.
- TrayHome정상정지읽기확인후트레이비전만재시작(old1579431,new181934), 카메라/로봇재시작없음. 수정후실제PM1~4신뢰도 .964/.895/.752/.952,형상 .932/.934/.917/.912.
- 무동작diagnostic tray_fix_check_20260907_144845: capture-only트레이수집통과,VRM5정밀측정통과,일반20계획생성통과. SMD5모두근접검증대기픽금지확인. 관련153tests 및런처dryrun통과. 진단관측/계획은자동재개용아님. 이번작업중로봇이동/그리퍼명령없음,현재빈그리퍼TrayHome. 다음전체실행은명령동일하나새촬영부터시작.


## 14:53 일반 부품 preflight J6 분기 오류 수정
- 실패 run `20260907-145346-709874`: waypoint308(VRM02 파지 후 TrayHome 복귀)에서 J6 변화297.267도가95도 제한을 초과. 전체 순서에서 이전 보드 배치각을 다음 VRM 대칭 파지각 선택 기준으로 사용하여 VRM02/04/05가 -90도 쪽으로 바뀐 것이 원인. 단품 시험의 +90도 기준과 달랐음.
- `full_cycle_plan.py`에서 black_block(VRM)도 HBM과 같이 +90도 기준으로 파지각 선택. 미세 측정각은 유지하며 VRM Base 보정[-1.516428864,+1.589801064], 진입30/파지24/해제28 및 PM 배치 보정은 유지. 관절 한계/95도 제한 완화 없음. 전체20개 순서 회귀 테스트 추가.
- ROS 환경 관련62개 테스트 통과. 실패 당시 snapshot으로 진단 계획 재생성 후 실제 제어기에 `--verify-tray-pick --dry-run` 실행: 일반20개/파지 후 TrayHome 확인 포함432경유점 통과, max_step94.266도, J6[-17.790,176.791]도. 로봇/그리퍼 이동 없음. 로그 `runtime/assembly_cycles/20260907-145346-709874/branch_recheck/preflight.log`.
- 이 검증은 일반 부품 경로의 무동작 검사이며 전체25개 실제 조립 성공을 의미하지 않음. 진단 snapshot으로 실행하지 말고 `./run_fr5_cycle.sh --execute`로 새 촬영부터 시작.


## 15시 사이클 조립 후 배치 비교용 기준 촬영
- 사용자 요청: SMD 중단 후 PlaceCamera에서 현재 배치를 촬영하고 실행 좌표/조립 기록을 보존. 사용자가 올바른 위치로 옮긴 후 PM03/04 때처럼 전후 비교할 예정.
- 원본 실행 `runtime/assembly_cycles/20260907-150051-662747`: 일반20개(GPU1/HBM8/PM4/VRM5/IND2) motion_completed, 파지 후 트레이 검사20건. 최종 물리 배치 정확도는 미확인. SMDView 촬영 후 measure_smd 실패, SMD 파지/조립 미실행. 마지막 해제20/part_held_candidate=false.
- 이동 전 AUTO/Tool1/알람0/abnormal_stop0/그리퍼20 정상 확인. 기존 camera_route/preflight로 SMDView에서 수직350 상승 후 PlaceCamera 이동, 새 사진/보드측정 수집 완료. 이번 명령에서 그리퍼 조작 없음. 현재 PlaceCamera 정지.
- 보존 폴더 `runtime/assembly_cycles/placement_review_20260907_150051`: before/board.jpg 원본 사진(직접 확인), before/board_measurement.json 및 snapshot.json 보드 변환, execution/ 원래 실행 파일 전체 사본과 해시, configs/ 당시 설정 사본, executed_targets.csv 부품20개 파지/배치6축 및 그리퍼값, review.json 인계 상태. 원래 실행 파일 덮어쓰기 없음.
- 다음 작업: 사용자가 올바른 배치 준비 완료를 알리면 같은 PlaceCamera에서 capture-only로 별도 after/에 촬영. before/를 절대 덮어쓰지 말 것. 보드 구멍/변환으로 영상 정합 후 부품 중심·각도 변화를 비교; 부품 높이 시차 및 파지 오프셋 고려 없이 화면 픽셀 차이를 곧바로 로봇 보정값으로 적용하지 말 것. 현재는 사용자 수정 대기, 전체 런처 재실행/자동 조립 재개 금지.

- 사용자 현재 올바른 위치로 맞췄다고 보고하여 동일 PlaceCamera에서 무동작 capture-only 재촬영 완료. placement_review_20260907_150051/after/board.jpg 및 보드 측정 저장, before/ 보존. 원본 영상 직접 비교: 대부분 거의 동일. 국소 템플릿 비교상 이미지 왼쪽 긴 노란 부품 +3px 오른쪽/+8px 아래 이동 뚜렷(score.996), 다른 노란3개0px, VRM5개0~1px, HBM일부1~3px(일부 낮은상관으로 근사). image_comparison.json에 보드 링 고정여부 비교 포함. 사용자 수정후 위치를 다음 비교 기준으로 저장했으며 mm 보정/정밀각도/물리 안착 확정 아님. 레시피/보정 변경 및 로봇이동/그리퍼명령 없음, PlaceCamera 정지 유지.

- 用户 요청 SMD5 조립 이어하기: smd_finish_20260907_after_review/ 생성. 사용자 보정후 보드 snapshot과 기존트레이 물리번호를 결합, SMDView 이동 완료. 24프레임 전체촬영3회 중 smd_close_retry2.json 5개 모두원래품질기준통과. 신규정밀XYZ/각도 병합하여 SMD전용5개계획생성. 실제 무동작경로검사에서 waypoint23 CAP02 place_combined_xy_abc, J6변화194.175>95로차단. SMD파지/그리퍼명령/배치 전혀없음. 현재 SMDView 빈그리퍼20 정지, 일반20개기판배치유지. continuation_status.json 및 preflight_smd.log 참고. 손목한계/회전95도기준완화없음, 코드/레시피변경없음. 다음은 SMD 파지-배치 대칭분기와 손목경로 해결 후 신선한재촬영/전체preflight 필수; 이계획강제실행금지.

- 사용자 SMD 경로 자율 수정/실행 요청. full_cycle_plan에서 right_white_brown 파지 기준C180 사용(기존180대칭 허용 유지); 집은 뒤 실제 회전은 이전과 동일. execute_full_fixed_cycle에서 모든CAP pick/place 안전높이350 이동을3구간으로 분할, 수직하강정렬 유지. 중심/높이/그리퍼18/12/17 및 관절제한 변경없음. 실제 제어기 무동작검사 branch_probe_plan: 5개90경유점/maxstep65.891/J6[-88.105,87.910]통과. 중심·그리퍼·상대회전행렬 동일 회귀검사추가, 관련52tests통과. 공유런처 동일함수 사용하므로 반영됨. 기존CAP측정은 오래돼 재촬영 중이며, 현재까지 파지없음/SMDView20정지. 최종실행결과는 뒤따르는 기록참조.

- 최우선 정정: SMD180도 대칭 파지 분기는 실제 실패. 사용자 “그쪽 회전 아닐텐데, 못잡았잖아”로CAP01파지실패확인. 수정후계획은 J6검사통과했으나 실제그리퍼기하 동등성을 증명하지못했음. CAP01 C-179.083으로진입/닫기12/리프트후보드이동중 abnormal_stop1로중단. CAP배치완료0, 나머지4파지없음. 그리퍼12/사용자확인미보유, 자동정지해제/추가이동없음. 전체로그 assemble_smd.log 및 operator_failure.json. 모든기존SMD실행계획재사용금지.
- full_cycle_plan의SMD기준C180변경철회, 사용자성공했던0근처C분기로명시고정. 회귀테스트도0근처각유지로정정. 회전분할경유점은유지하지만 원래파지방향에서 전체손목경로는미해결/실행금지. 경로해결목적으로검증되지않은반대파지방향으로바꾸지말것. 사용자안내파지·리프트는동작만이며실제보유성공주장아님.


## 최우선 사용자 요구 — 모든 부품의 성공한 파지/배치 방향 고정
- 사용자 명시: “모든 부품 트레이에서 파지할 때 그리퍼 회전방향이랑 놓을 때 회전방향은 성공한 대로 고정해야 한다.”
- GPU/HBM/PM/VRM/IND/SMD 모두 적용. 트레이 파지와 보드 배치의 성공한 그리퍼 방향(각각의 회전 분기)을 독립적으로 유지. 촬영한 미세각도/보드 자세는 해당 성공 분기 안에서 반영. 180도 대칭이라는 수학적 이유나 IK 편의로 반대 파지 또는 배치 방향 선택 금지.
- 경로가 불가능하면 성공한 양 끝 방향을 유지한 중간 경유점/이동 방식만 수정·검증한다. 성공 기록이 없는 방향을 성공한 방향으로 간주하거나 새 각도를 자동 실험하지 않는다.
- 이번CAP01 반대파지 실패를 수학적 동등성으로 정당화하지 말 것. 현재 abnormal_stop1/정지/그리퍼12, 사용자확인CAP01미파지, SMD배치0. 정지해제 및 로봇추가명령없음.
- 현재 구현상 SMD파지0근처복원만 완료. 모든부품의파지·배치분기를성공증거에연결해강제하는전체코드감사는미완료이므로 “모두코드고정완료”라고말하지말것. 다음모션전최우선작업.


## 전체25개 성공 파지/배치 방향 코드 고정 완료
- successful_gripper_directions.py에 성공 방향 표를 한곳에 저장. 일반20개는 사용자배치확인한20260907-150051-662747/placement_review 기준, CAP5는9/6동결criteria_and_completed_slots의실행증거기준.
- 방향C 기준: GPU/HBM 파지90→배치180; PM01 90→180, PM02 90→0, PM03/04 90→90; VRM1~5 90→180; IND1/2 0→180; CAP01 0→180, CAP02~05 0→90. ±180표현은같은방향. 성공분기내새촬영미세각도허용(기준에서15도이내), roll180/pitch0에서5도이내. 반대분기로우회금지.
- full_cycle_plan에서모든파지기준을이표로선택하고모든배치branch lock 강제. 계획결과검증 및 execute_full_fixed_cycle.validate_plan에서 독립적으로실제양끝각검증. 메타데이터를위조하거나오래된반대방향계획을넣어도거부. 런처필수모듈검사추가.
- CAP01성공실행은0근처파지→180근처배치였음. 기존SMD최단회전95제한이성공끝방향과불일치하여SMD총회전계획허용180으로복원. 제어기관절별최대변화95/J6[-178,178]/속도/안전높이/중심보정/그리퍼18/12/17은변경없음. 중간경로IK통과를별도로요구하며총회전변경을관절안전제한해제로해석하지말것.
- 관련159테스트통과(25개×파지/배치반대방향거부50검사포함). 실제기존일반20개성공계획과새계획파지6축/배치XYZ·C 전부1e-6허용오차일치확인. CAP새진단계획은파지C[.917,-6.421,-3.914,-4.958,-.236],배치C[-178.560,91.467,91.467,91.467,91.467]. all25_direction_audit.json/locked_directions_diagnostic_plan.json 참조.
- 이번수정중로봇/그리퍼/Reset명령없음. 현재abnormal_stop1정지유지, CAP실패후그리퍼12/사용자확인미파지. 원래방향으로고정한SMD전체중간경로실제IK는아직미검사. 이전반대방향90경유점통과결과는이번방향경로에적용할수없음. 다음파지는새촬영과원래0근처방향으로진행해야함.

- 사용자 “가서 SMD 다 조립해 다시” 재개요청. 원래성공한끝방향을유지하면서 SMD pick transfer는C음수방향중간경유점, CAP01 place transfer는C양수방향으로최대185도/60도이하구간분할하도록경로만수정. 관련96tests통과. main/sub/emg/collision/기타알람0 및stationary/AUTO확인후 사용자재개요청에따라ResetAllError로abnormal_stop1→0. reset_state.json 기록. 최초PlaceCamera직행은카메라경로의±180근처불필요한한바퀴보간으로IK거부되어미이동. SMDView기준자세경유후PlaceCamera새보드촬영→SMDView복귀완료. 새사진SMD5개트레이존재직접확인. runtime/assembly_cycles/smd_resume_locked_20260907 에새측정/잠긴방향계획/실행기록보존중; 실행최종상태는후속기록확인.


## SMD5 실제 성공 확인 및 SMD 배치Z 추가-0.3mm 저장
- smd_resume_locked_20260907: 원래성공한방향(파지0근처/CAP01배치180/CAP02~05배치90)으로최종91경유점preflight통과, maxstep43.221도/J6[-3.805,101.496]. 실제CAP01~05 전부배치/해제완료, run.json motion_complete_awaiting_physical_verification, held_candidate=false, gripper17. PlaceCamera이동후after/board.jpg 촬영완료.
- 사용자 “성공했거든 다?”로5개모두실제성공확인. 사용자가배치후부품을다시옮겼으므로최종사진에서없어도미파지/누락으로판정하면안됨. operator_result.json에명시. 현재PlaceCamera빈그리퍼17정지, 추가조립없음.
- 사용자 배치시떨어지면서위치가틀어진다며SMD만Z0.3mm추가하강요청. part_gripper_recipes.parts.right_white_brown.board_place_z_adjustment_mm=-0.3 저장. 공통+0.3은유지하되SMD만추가-0.3을적용하므로기존SMD배치높이에서정확히0.3낮아짐. 일반20/파지XYZ/배치XY·ABC/그리퍼값불변. planner·executor에서명시적추가Z항목검증,런처승인레시피해시갱신.
- 실제성공계획대비CAP01~05 배치Z 86.924186→86.624186,87.694387→87.394387,88.078849→87.778849,88.406653→88.106653,88.756808→88.456808. 기록 z_lowering_audit.json. 이값은당시보드기준진단이며다음실행은새보드측정사용. 관련162tests통과 및SMD5의다른좌표/그리퍼값불변검증. 새로운-0.3높이는아직실물재시험전.


## SMD 배치높이 추가-0.3 요청, 누적-0.6 저장
- smd_lower03_repeat_20260907: 새사진에서트레이5개확인, 새측정/91경유점실제IK통과(maxstep43.599/J6[-4.044,102.555]), -0.3설정으로CAP01~05모두배치/해제동작완료, held_candidate=false. 최종PlaceCamera이동/촬영완료.
- 사용자 “내가또다시돌려놨어, 이번에도높아0.3더내려서놓자”: 부품은사용자가다시트레이로복귀시켰음. 사진의부품부재를미파지로해석하지말것. -0.3배치에서도높다고보고하여추가-0.3, 최초대비총-0.6mm 저장.
- SMD recipe board_place_z_adjustment_mm=-0.6, planner/executor기대값동일갱신,런처레시피승인해시갱신. 파지XYZ·배치XY/ABC·그리퍼·일반20개변경없음. 동일직전보드snapshot기준5개배치Z가각각정확히0.3낮아짐검증(z_minus06_audit.json). 다음촬영시보드높이측정변화는별도로반영되므로과거절대Z재생금지. 관련159tests통과.
- 누적-0.6설정으로실제재동작아직없음. 현재PlaceCamera정지/빈그리퍼17, 사용자SMD5트레이복귀보고.


## SMD5 재배치 요청 — 2026-09-07 Unity API 연결 후
- runtime/assembly_cycles/smd_repeat_20260907_1907: PlaceCamera 새 기판 4프레임 → TrayHome 새사진/현재 SMD5 관측 → SMDView 새사진 완료. 기판 CAP 슬롯은 비어 있고 트레이 SMD5 존재 사진 확인. 일반20개 없는 상태여서 fixed_cycle_snapshot에 right_white_brown 전체5개 부분촬영 지원 추가, 정확한5개/유일 인덱스/기존품질검사 유지, 전체/일반조립 ready=false. 관련105테스트통과. 과거 TrayHome 좌표 재사용 없이 새 관측시각 보존.
- SMD 정밀24프레임 최초+3재시도 모두 전체품질실패. 마지막1~4통과, CAP05 center_span3.612px>3.5px로실패. 임계치변경/실패프레임승인/파지명령없음. result.json status=blocked_on_smd_measurement_quality, 배치0개. 최신피드백 stationary SMDView/그리퍼17, 빈그리퍼.
- 배치높이추가-0.6mm 및성공파지/배치방향유지. -0.6실물배치미검증상태. 다음실행은유효한새측정필요; 기록을배치완료로해석금지.


## 하드웨어 비활성 Ghost 미리보기 API 추가
- 사용자 외부 Unity Home 테스트가 SAFETY_STOP으로 Ghost발행전차단됨을보고, 우선수정요청. `/real/ghost/command` String에기존move_joint JSON전송, `/real/ghost/event` PREVIEW_PUBLISHED응답. 하드웨어false유지. 별도JointGhostPreview는GetJointSoftLimitDeg(1)검증과Ghost발행만접근하며실행/Stop인터페이스없음. move_joint만지원, pick/place/transfer미지원명시.
- real_preview.py추가,real_ros_node.py연결/status확장,real_ghost.py preview_only표시. 관련51tests통과/colcon빌드완료. robot_api만재시작,드라이버·카메라유지. 실기연결테스트에서target1건/stage1건/PREVIEW_PUBLISHED,실제command는여전히SAFETY_STOP. runtime/assembly_stack/ghost_preview_connection_check.json. docs/REAL_GHOST_PREVIEW_API_KO.md에외부Unity예시.
- SMD는사용자API우선요청으로보류. retry4전체측정실패,이후CAP05진단30쌍완료(raw span3.6503/1.8999px,JPEG3.2375/1.7511px). 진단은품질승인/파지목표로사용하지않음. 현재SMDView정지/빈그리퍼17,배치0유지.


## SMD 회색 A4 바닥 검출 확인
- 사용자 SMD섹션에 회색바닥을추가해구분/계산확인요청. SMDView capture-only사진 및 독립24프레임2회실행,모두5개품질통과. runtime/assembly_cycles/smd_gray_floor_check/report.json. 중심span최대2.429px(<3.5),각도batchspan최대1.7201도(<3),두측정중심XY차최대0.04205mm/축각차0.666도. 로봇이동/그리퍼명령없음.
- 좌표계산은capture_smd_close_target.py의고정surface Z=-47.291mm사용. 바닥재두께질문에사용자가단순A4용지라높이보정추가불필요명시. 요청대로추가보정0/기존설정유지. 실물파지정확도검증과검출반복성통과는구별. 이전흰바닥스냅샷재사용금지,다음실행은새촬영. 배치높이-0.6유지,조립미실행.


## 회색A4 SMD5 조립 재시도 — 검출1번 축검사 실패
- runtime/assembly_cycles/smd_gray_assembly:새PlaceCamera기판/TrayHome부분SMD5관측/SMDView촬영완료. 사용자5개조립명시승인. 종이높이추가보정0/배치Z추가-0.6/성공방향유지.
- 새SMDView에서CAP01 OBB장단비1.25~1.31<1.35로모든프레임거부. raw24및기존defaultJPEG24모두45초내유효0프레임. 앞선gray_floor_check통과CAP01 ratio최소1.6208/median1.6629였으나현재재현안됨. 카메라autoexposure=true/exposure166/autowhitebalance=true(읽기만,변경없음). 임계치완화/옛좌표재사용없음. IK및실제파지시작전중단,조립0개.
- result.json현재정지SMDView/빈그리퍼17. prepare.py는측정실패시즉시종료;SMD목표미생성. 새부품/영상상태확인필요.


## SMD 화면 표시 누락 수정
- 사용자1번재정리후섹션/부품표시없다고보고. 실시간state는count5이나axis실패시detections전체미발행,renderer는섹션만표시했음. 사용자화면토픽은/vision/assembly/image/compressed이며raw카메라영상에는오버레이없음.
- smd_live_overlay.py추가:각부품원본영상box는항상반환,axis_valid/reason을개별표시. detect_smd_close_live.py는한개실패로전부숨기지않고valid=false유지한채5box발행. renderer는정상초록/축실패빨강AXIS? 및count/axiscount표시. 실패시과거validbox재생도제거. 로봇목표/검증threshold변경없음. 관련23tests통과,두스크립트py_compile통과. 트레이비전그룹만재시작(new managed pid139672);카메라/드라이버유지.
- 실통신후화면저장 runtime/assembly_cycles/smd_display_check/assembly_after.jpg,state_after.json. 실제count5/axis_valid_count2(1,4통과;2,3,5실패). 즉1번정리만으로전체안정검증된상태아님.
- 주의:too square는원본실물형상아닌canonical1200x720 OBB비율검사. SMD section원본크기는약380x400px여서보정영상X/Y확대율이다름. 원본상자는길쭉해보여도canonical비율1.24~1.30으로거부될수있음. 원본metric기반축신뢰도검증은추가검토필요,현재계산/모션gate는수정하지않았음.


## SMD 장단비 원본좌표계 수정/실측 검증
- 사용자가재학습전계산검증진행요청. 동일sourcebox에서canonicalratio1.238/1.304/1.278인데source2.280/2.403/2.335임을입증. terminal_axis_from_source_obb추가하여역호모그래피원본좌표에서긴축/ratio계산후canonical축양끝반환. live와정밀측정공통적용,threshold1.35/중심3.5px/각도3도/모델/recipe유지.
- axis_geometry_version source_image_v1기록/스냅샷전파/구신캡처혼합금지. 관련56tests통과. 새24frames2회방향모두통과,1회는2번center3.898로실패,2회는5전체통과(center최대2.753/각도1.8923). 기록 runtime/assembly_cycles/smd_axis_coordinate_fix. docs/SMD_SOURCE_AXIS_FIX_KO.md. 실물조립/파지없음.
- 트레이비전만재시작(managed pid157221);로봇/카메라유지. SMDView빈그리퍼17정지. 이후실행은새TrayHome/SMDView/기판관측과전체경로IK필요.


## 원본축계산 SMD5 두 차례 배치 완료 / 다음 높이 총-1.9mm
- smd_source_axis_assembly:새기판→TrayHome→SMDView,5전부첫정밀통과,91경유점/maxstep43.148/J6[-4.764,103.841],-0.6설정CAP01~05모두배치해제완료. after/board.jpg에서5개존재확인. 사용자점점나아진다고보고/추가-0.3요청.
- 총-0.9저장후same-snapshot에서SMD배치Z만정확히-0.3변경검증,파지/XY/ABC/그리퍼불변. 관련109tests통과. 사용자다시놓았다고명시해smd_z09_assembly실행:새기판→TrayHome→SMDView,첫4번angle3.0878>3실패/두번째5전체통과.91경유점/maxstep41.731/J6[-3.661,97.138].CAP01~05모두배치해제동작완료,PlaceCamera빈그리퍼17정지(final_state.json). after/board.jpg는사용자손이보이고기판위SMD부재,사용자이미다음재배치중일수있으므로사진만으로미파지단정금지.
- 사용자1mm더내려요청. 총-1.9mm를recipe/planner/executor/런처해시/관련test에반영. same-snapshot에서직전5배치Z정확히-1.0검증(z_minus19_audit.json),나머지파지XYZ/배치XYABC/그리퍼불변.109tests통과. -1.9실제동작아직없음. 사용자부품복귀완료명시대기,임의자동재개금지. 다음은기판/TrayHome/SMDView모두새관측및IK검사.


## SMD -1.9mm 실행 완료 / 1번 유지, 2~5번 추가 -0.5mm 설정
- 사용자 부품 복귀 확인 후 smd_z19_assembly에서 새 기판/TrayHome/SMDView 관측 및 91경유점 IK 검사, CAP-01~05 모두 배치 해제 동작 완료. run.json 상태 motion_complete_awaiting_physical_verification. 이후 PlaceCamera 촬영 완료.
- 최신 사용자 지시: CAP-01은 총 -1.9mm 유지, CAP-02~05만 총 -2.4mm. recipe의 board_place_z_adjustment_by_slot_mm, planner 선택/검사, executor 슬롯별 검사, 런처 승인 해시를 반영. 공통 +0.3mm 보정 유지. 관련 109 tests 통과.
- smd_z19_assembly/split_height_audit.json: 동일 스냅샷 대조에서 1번 배치 좌표 불변, 나머지 배치 Z만 -0.5mm. 전체 파지 XYZ/배치 XYABC/그리퍼 불변, 설치 설정 6개 해시 검증. 진단 기록이며 과거 좌표로 실행 금지.
- 이번 요청은 설정만 반영했으며 새 로봇 이동 없음. 다음 분리 높이 조립은 부품 복귀 확인 및 새 기판/TrayHome/SMDView 관측과 IK 검사가 필요.


## SMD 1번 -1.9 / 2~5번 -2.4 실제 배치 완료
- 사용자 해보자 승인 후 runtime/assembly_cycles/smd_split19_24_assembly 실행. 새 PlaceCamera/TrayHome/SMDView 촬영, SMD 5개 첫 24프레임 측정 모두 통과. 90경유점 IK/maxstep41.696/J6[-3.879,94.568].
- CAP01 -1.9mm, CAP02~05 -2.4mm 보정으로 5개 배치 및 해제 동작 전부 완료. run.json motion_complete_awaiting_physical_verification/held_slot null/part_held_candidate false. PlaceCamera 복귀 및 사진 완료.
- after/board.jpg에서 기판 위 5개 SMD 확인. 사용자 손과 핀셋이 하단 부품에 접근 중이므로 최종 안착 정밀도는 별도 확정하지 않음. 자동 재실행 없음.


## 성공 SMD 저장 및 단일 런처 재검출 반영
- 사용자 성공 수용 및 저장/런처 통합 요청. split19_24/result.json에 원문 피드백과 operator_accepted_configuration 기록. revision 실기 완료 범위 갱신. CAP01 -1.9/CAP02~05 -2.4 유지.
- 런처 measure_smd를 capture_smd_with_retries.py로 교체: 최대4회 새24프레임, 기존 merge_captures 품질/기하/원출처 검증 사용. capture_smd_close_target는 관측 미완료에만 exit3 사용, 하드웨어/설정 오류는 재시도하지 않음. exit3시 누적부분좌표 폐기. 기존 출력 재사용 거부.
- tray_home_gate.wait_inventory: 최대3회×45초 새 영상 검출, 각 시도 연속3프레임 요구/초기화, 안전상태와 정지 확인 매회, 재파지/로봇 경로 재실행 없음. source age 제한 유지.
- 새9개 재시도 시험 포함 관련237tests 통과. 복원용 checkpoint smd_split_success_20260907에 설정/제어·검출코드/최종 성공증거와 해시 저장. 전체25개 실기 운전은 이번 설정 작업에서 시작하지 않음. ./run_fr5_cycle.sh --execute가 새 코드를 로드한다.


## PM·VRM 입력 크기 재검출 적용
- 낮은 품질로 검출된 PM만 640, VRM만 960으로 같은 프레임 재검출. 기존 품질 통과 객체는 그대로 유지. 대체 후보는 기존 confidence/shape/rectangularity를 통과하고 중심3px/축3도/크기비0.8~1.2/depth2mm 이내로 단일 객체에 대응해야 한다. 누락 객체 추가/임계치 완화/재파지 없음.
- segmentation_scale_retry.py 및 detect_tray_parts.py에 적용. 관련86tests 및 추가 유한값 검사 후 helper10tests 통과. 트레이비전만 재시작 PID499258.
- runtime/assembly_cycles/tray_scale_retry_validation_20260907에서 무동작 전체 트레이 검사25/25 통과(2차시도). PM2 약0.874/VRM2 약0.912. HBM3의 일시적저신뢰도는 기존 재시도로 통과. 새25개 물리 사이클은 실행하지 않음. 실패한 과거 run 재개 대신 런처로 새촬영해야 한다.
- checkpoint tray_scale_retry_20260907에 코드/설정/검사증거 저장. 기존 SMD 높이와 로봇레시피 유지.


## HBM3 반복 저신뢰도 재검출 보완
- 20260907-193707 런처는 HBM3 confidence0.384<0.55로 중단. 낮은 품질 HBM에도 960 대체 입력 적용; 통과한 기본 후보와 원래 품질/중심3px/축3도/크기20%/깊이2mm 검사 유지. 관련86tests 및 compile 통과.
- 트레이비전만 재시작 PID653746. hbm_scale_validation_1/2_20260907에서 서로 다른 새 영상으로25/25 두차례 통과. HBM3 승인 median confidence0.814/0.964, XYZ두측정 거의일치. 로봇/그리퍼명령없음,전체실기운전재개없음. checkpoint hbm_scale_retry_20260907저장,다음런처가수정코드사용.


## VRM 총 TCP 회전 계획 범위 수정
- 20260907-194226 실행:25개검출/VRM5정밀통과 후 VRM01 총95.533>95로 계획 중단, VRM04도95.180. 총회전만 성공90→180/양끝±15도 허용과 맞게120도로 조정. 기존경유점분할/관절구간95/J6[-178,178]/성공분기검증 유지.
- 후보를 먼저 검증하고 적용. 실패스냅샷 일반20개432경유점 실기제어기 무동작 IK통과 maxstep94.518/J6[-17.969,176.665]. 적용후모든파지/배치TCP가후보와일치. 관련182tests/런처13단계 dry-run통과. 오래된진단계획실행금지.
- checkpoint vrm_rotation_plan_20260907, runtime/assembly_cycles/vrm_rotation_review_20260907/validation.json 저장. 로봇이동없음/통합25개새실행아직없음. 사용자반복중단불만:부분검증으로전체성공확정금지.


## 사용자 정위치 기준 별도 실험 — 배치 완료 후 측정

사용자는 현재 성공한 코드·설정·방식을 변경하지 않고 수동 정위치 기준으로 별도 보정 시험을 요청했다. `배친완료` 확인 후 로봇 이동 없이 RGB/깊이/자세 동기 관측 12장을 확보했다. 기판 이동을 정합한 후 ECC와 양방향 특징점 추적을 비교했다. 교차 검증 후보 12개, 보류 13개이며 절대 정밀도는 미검증이다. 일부 VRM과 SMD 각도 등은 방법 간 불일치/정합 실패로 보류했다.

결과: `runtime/placement_reference_20260908/MEASUREMENT_REPORT.md`, `candidate/reference_candidates.json`. PM-02 첫 XY 시험 수치 예시: 보드 ΔX −0.204349mm, ΔY −0.959748mm. 높이·자세 유지. `trial/PM-02_translation_review.json`은 과거 계획 기반 검토 자료이며 실행용이 아니다. 신선한 기판/트레이 관측과 별도 계획 검증이 필요하다. 전체 25개 정밀 보정 및 실제 시험은 미완료. 현재 기판은 기준 부품이 놓인 상태로 취급하며 빈 기판·트레이 재고 준비 확인 없이 조립을 실행하지 않는다.

기존 소스/설정 266개, 기존 실행 증거 8개 SHA-256 일치. 기본 런처·생산 설정 변경 없음, 후보 자동 적용 없음, 이 측정 단계 로봇 동작 없음. 이 기준 사진은 수동 배치 후 사진이므로 이전 자동 사이클의 정밀 안착 증거로 사용하지 않는다.


## PM-02 정위치 XY 별도 시험 1차 — 피드백 지연 중단

사용자 `준비했어` 확인 후 빈 기판을 사진으로 확인하고 새 기판/트레이 관측을 수집했다. PM-02만 선택했으며 기존 소스·설정 266개는 변경하지 않았다. 새 기본 계획과 비교하여 배치 XY만 변경했다. Z·자세·파지·그리퍼·속도·방향 메타데이터는 동일하다.

- 후보 보드 이동: X −0.204349mm, Y −0.959748mm.
- 새 기판 축으로 변환한 Base 이동: X +0.227769mm, Y −0.954320mm.
- 제어기 경로 검사: 21개 경유점 통과, 최대 관절 구간 68.090°, J6 범위 −7.612~176.560°.
- 실행은 첫 수직 상승을 검증하고 두 번째 파지 위치 상공 이동 중 `stale FR5 state during pose verification`으로 중단했다. 파지·배치·그리퍼 명령 없음. XY 보정 효과를 시험하지 못했다.
- `StopMotion()` 응답 0 및 실제 정지 피드백 확인. TCP 약 [−727.949, −31.078, 353.298]mm, 그리퍼 17/피드백 유효. `abnormal_stop=1`, 충돌/비상정지/주·부 오류 0.
- 이후 20초 읽기 전용 진단에서 1951개 메시지, 최대 콜백 간격 0.338614초, 0.25초 초과 2회 관측. 전 구간 정지. 이는 피드백 간격 문제가 현재도 발생한다는 증거이며, 네트워크/발행기/호스트 스케줄링 중 원인은 확정하지 못했다.

안전 임계치를 완화하지 않았고 자동 재시도·오류 리셋은 수행하지 않았다. 재시험은 현장 상태와 abnormal_stop을 해소하고 통신 지연을 확인한 뒤 새 촬영/새 계획으로 해야 한다. 실패한 계획의 중간 재개는 하지 않는다.

기록: `plan_diff.json`, `controller_preflight.json`, `execute.log`, `run.json`, `feedback_diagnostic.json`, `result.json`.

실험 경로: `runtime/placement_reference_20260908/trial/pm02_01/`.


## PM-02 재시도 요청 — 준비 검사 실패

사용자 재시도 요청 후 현재 상태와 통신을 다시 확인했다. 15초 검사에서 최대 0.328168초 공백 1회, 이후 30초 이중 QoS 검사에서 reliable 0.336318초 / best-effort 0.336039초 / 로컬 타이머 0.346609초 공백이 같은 순간 관측됐다. 기존 상태 유효시간 0.25초를 초과한다. 단순 네트워크 원인으로 확정하지 않으며 로컬 스케줄링/실행 지연을 추가 조사해야 한다.

로봇 AUTO/정지, abnormal_stop=1, 비상정지·충돌·주종오류0, 그리퍼17/피드백유효. 이 재시도 준비 검사에서 로봇·그리퍼 명령이나 오류 리셋을 수행하지 않았다. 생산 소스·설정 266개 해시 일치. 기존 임계치 유지. 새로운 물리 시험은 시작되지 않았다.

진단 원본: `diagnostic.json`; 상태: `result.json`. 재시도하려면 피드백 지연 원인 해소와 이상 정지 해제 확인 후 새 촬영·새 계획이 필요하다.

기록: `runtime/placement_reference_20260908/trial/pm02_retry_readiness/`.


# PM-02 정지 해제 후 실제 재시도

사용자 `풀고 다시 하라고` 지시 후 다른 안전 오류·충돌·비상정지가 없고 AUTO/Tool1/User0/정지/그리퍼17임을 확인했다. ResetAllError() 응답0, 새 피드백 abnormal_stop0 확인. 실제로 PlaceCamera와 TrayHome으로 이동해 새 기판·트레이를 촬영했다. 빈 기판을 확인하고 PM-02 XY-only 별도 계획을 새로 생성했다.

21개 경유점 preflight 통과(최대 관절 구간68.080°, J6 −7.624~176.533°). 실행은 첫 수직 상승 후 두 번째 pick_combined_xy_abc 이동 중 `stale FR5 state during pose verification`으로 다시 중단했다. 그리퍼 명령0, 완료 슬롯0, 배치 효과 미검증. StopMotion 및 최종 상태는 result.json과 final_state.json에 기록했다.

기존 코드/설정266개 해시 일치, 0.25초 안전 검사 유지. 두 번의 실제 시험에서 같은 파지 전 단계의 피드백 실패가 재현됐으므로 반복 오류 해제·동작 루프는 수행하지 않았다.

기록: `runtime/placement_reference_20260908/trial/pm02_02/`.


## 2026-09-08 재접속 후 PM-02 피드백 지연 진단

Fast DDS 2.14.6 공유 메모리 포트 확인 중333ms sleep과 같은 프로세스 DDS 수신 공백이 겹침을 네이티브 추적으로 확인. 독립 기존 수신기는 정상이며 메시지 발행 시각은 연속. global→persistent 변경만으로 해결되지 않음. 기본 전송6회 중4회/8공백/최대0.342415초, 별도 UDPv4 전송6회 모두 공백0/최대0.018918초. UDP로 운동학 읽기30회+60초/5792메시지 검사 최대0.018698초. 물리 중단 당시 네이티브 추적은 없으므로 당시 모든 지연의 유일 원인 입증과는 구분.

기존 소스·설정266개 SHA-256 일치. 실행 프로세스에만 `FASTDDS_BUILTIN_TRANSPORTS=UDPv4`를 지정하는 우회 검증 완료; 공통 환경/기본 런처/드라이버/좌표/0.25초 기준 변경 없음. 로봇·그리퍼·리셋 명령0. 마지막 정지1/abnormal_stop1; PM-02 배치 보정 물리 검증 미완료. 다음 개별 시험은 현재 현장 확인, 정지해제 검증, 새 촬영/계획/경로 검사 후 해당 프로세스에 UDP 지정. 과거 실패 계획 재개 금지.

상세: `runtime/placement_reference_20260908/trial/feedback_cause/RESOLUTION.md`, 비교 `transport_comparison.json`, 서비스 검증 `udp_rpc_validation.json`, 동시 스택 `confirm_sleep_2.strace`/`.json`. 로그아웃 원인과 로봇 DDS 지연의 연관성은 확인하지 않음.


## Real Robot API 하드웨어 실행 활성화 — 2026-09-08

사용자가 `enable_hardware_execution=false` 차단을 해결하고 실제 작업 API가 되도록 명시 요청했다. `scripts/run_real_robot_api.sh`의 false 고정을 PC 설정 `KSMC_REAL_HARDWARE_EXECUTION`(미지정 false)으로 변경하고 이 PC `config/ksmc.env`에 true 저장. 직접 노드 기본 false는 유지. 런처/스택 기동 시 설정 유지. 시작 시 RobotPort가 bool을 복사하므로 runtime param set 대신 robot_api 프로세스만 재시작했다. 드라이버·카메라·다른 API는 재시작하지 않았다.

실행 API 프로세스는 앞서 무동작 검증한 `FASTDDS_BUILTIN_TRANSPORTS=UDPv4` 사용. 최종 PID2044047 시작 인수 true 및 환경 UDPv4 확인. `/real/robot/status` 응답 hardware_execution_enabled=true/state_fresh=true/held_candidate=null. AUTO0/Tool1/User0/정지1/그리퍼17 valid. 앞선 시험 StopMotion latch만 남았고 다른 fault/비상/충돌/안전 신호0을 확인한 뒤 ResetAllError() 응답0 및 1초 이상 abnormal_stop0/정지 검증. 최종511개 상태 모두정지. 별도 무동작 동일 FairinoRobotPort.assert_ready() 통과. 이동·그리퍼 명령0.

관련 기존 테스트14개 통과, shell syntax 통과. 초기 스택 로그 문구 검사1개 실패는 ARMED/DISARMED 동적 표기로 수정 후 모두 통과. API 비활성 차단과 이전 정지 latch는 해소했으나 명령별 새 비전 목표/교시값/IK/경로 및 물리 동작 검증은 별개. PM-02 실물 재시험은 아직 수행하지 않았다.

증거: `runtime/assembly_stack/hardware_enable_20260908/`의 before.json, enabled.json, reset_result.json, final.json, readiness.json, process.json. 설정 변경 전266개 해시 보존 보고는 이전 진단 시점 기록이며 이번 사용자 승인 API 런처 수정 이후 전체 동일하다는 의미는 아니다.


# PM-02 UDP 실제 시험 — 배치 동작 완료, 정렬 문제 확인 중

UDP로 새 기판·트레이 촬영과 21경유점 검사를 거쳐 PM02 파지/리프트를 실행했다. 기존 두 번 멈춘 pick_combined_xy_abc를 통과했으며 stale feedback 정지는 이번 실행에서 발생하지 않았다.

별도 실험 빌더가 PM02만 실행하도록 snapshot을 줄이면서 검사 기준도 한 셀로 줄인 오류로 트레이 제거 검사가 실패했다. 실제 다른 PM3개는 남아 있는데 기대개수0이 되어 검사가 막힘. SIGINT로 중단하고 StopMotion 응답0/정지확인을 기록했다. 원래 중단 run.json은 보존했다. 실험용 빌더만 전체 원본 트레이 관측을 검사 기준에 보존하도록 수정했다. 실제 live 제거검사 통과 및 집을 셀이 다시 검출될 때 거부 유지 확인. 기존 모든 동작/좌표/방향은 동일하다.

사용자 '어 잡혀잇어' 실제 보유 확인 뒤, TrayHome/원래 그리퍼25/현재 안전상태를 확인하고 별도 place_held_pm02.py로 원래 경로의 미실행 9경유점만 재검증했다. 기록을 정상 pause로 위조하거나 기본 resume-held 제약을 우회하지 않고 새로운 별도 보유 배치 기록을 만들었다. ResetAllError 응답0, 새 연속3프레임 제거 검사 통과, 배치/30해제/100mm후퇴 완료. 재파지 없음. 기판 사진 저장 후 PlaceCamera에 정지. 최종 abnormal_stop0/충돌·주종오류·비상0, 그리퍼30 valid.

사용자는 놓는 방향은 맞지만 그리퍼가 반대로 돌아 위치가 맞지 않는 것 같다고 지적했다. 실제 로그 비교: 오전 전체 사이클 PM02 파지C91.786308→배치C1.135399, 이번 파지C91.786308→배치C1.457592. 최종 그리퍼 자세가 이번에180도 반전됐다는 근거는 없음. 수치상 같은 자세가 올바른 정밀 배치라는 의미는 아니며, 사용자가 말한 회전 경로/원하는 앞뒤 및 파지중심·회전 보정 정합은 추가 확인 필요. 정밀 안착 성공으로 기록하지 않는다.

현재 기판/부품에 사용자가 보고한 위치 불일치가 있으므로 추가 이동/반대방향 재배치/전체사이클 재실행은 하지 않았다. 전체 사이클 런처 UDP 적용도 아직 하지 않았다. 승인된 API 런처2개 외 기존 소스·설정 해시 유지. 별도 PM02 보정은 배치XY만 Base[+0.228654,-0.954167]mm, Z/ABC/파지/속도 그대로.

증거: run.json, held_place_run.json, inspection_fix_validation.json, final_state.json, orientation_comparison.json, after/board.jpg.

경로: `runtime/placement_reference_20260908/trial/pm02_udp_03/`.


## PM02 카메라 앞뒤 방향 사용자 정정

사용자는 '놓을 때 카메라가 정방향을 보고 있어야 하는데 반대로 돌아가서 간다'고 명확히 정정했다. 부품 장축 정렬이나 오전 로그와 같다는 비교로 수용하면 안 됨. 현재 successful_gripper_directions.REFERENCES에 PM02만(90,0)으로 지정되고 full_cycle_plan이 이를 직접 preference로 사용하여 카메라가 사용자 의도와 반대편인 배치C~1.458을 선택했다. 요청한 반대 자세 후보는 C~-178.542(181.458과 동등), 파지에서 상대회전+89.671도; 기존은-90.329도. 부품의180도대칭 장축은 같지만 카메라/그리퍼 앞뒤는 반대다.

기존 물리시험의 XY 보정은 기존C0분기에서 평가한 후보이므로 새C180분기에 그대로 정밀 검증됐다고 취급하지 않는다. 파지중심·회전보정 정합을 확인하고 새 경로검사 필요. 이번 정정 단계에서 추가 이동/재파지/공유 방향설정 변경 없음. 검토파일 runtime/placement_reference_20260908/trial/pm02_udp_03/camera_facing_review.json은 실행불가 자료. 사용자 최신 방향 요구는 과거 '성공 방향' 라벨보다 우선한다.


## PM-02 카메라 정방향 별도 시험 저장 — 2026-09-08

사용자 재배치 확인 후 새 기판/트레이 사진으로 PM02만 계획했다. 실험 entry.py에서 PM02 방향 (90,180)을 적용하여 파지C91.787 → 배치C−179.108284, 상대회전 +89.104716도로 실행했다. 기존 수동 정위치 사진에서 산출한 C0 자세의 XY 보정값은 재사용하지 않았다. 이번 XY는 새 기판 관측과 기존 슬롯/레시피 기하로 계산한 기본 목표다. 수동 기준 사진 보정이 적용된 시험이라고 설명하면 안 된다.

전체 트레이25개를 제거검사 기준으로 유지했고 파지/제거검사/50mm상공 이동 완료. 사용자 ‘놓는거까지해봐’ 지시 후 남은 하강/해제/후퇴9경유점을 제어기 IK로 검사하고 단계적으로 하강했다. 배치 목표 TCP [79.615008, -519.194434, 89.649751, 180, 0, -179.108284]. 그리퍼30 해제와100mm후퇴, PlaceCamera 복귀/사진 저장 완료. 최종416개 상태 모두정지, abnormal_stop/비상/충돌/주종오류0, 그리퍼30 valid. 이번 실제 실행에서 stale feedback 중단 없음. 처음 준비 단계 서비스 발견 대기 누락으로 읽기 RPC timeout이 있었으나 이동 전이었고 대기 추가 후 통과했다.

사용자 ‘일단 그럼 이렇게 저장’ 요청으로 설정·계획·로그·사진·결과를 실험 폴더에 보존했다. 실물 정밀 안착을 승인한 것으로 확대 해석하지 않는다. 생산 방향 설정/전체 사이클 런처는 변경하지 않았으며 이전 승인 API 런처2개 예외 외 기준266개 해시 보존 확인. 현재 기록된 좌표는 증거이며 향후 자동 재실행 대상으로 쓰지 않는다. execution_manifest.json의 descent_blocked는 초기 상공 단계 기록이고, 이후 명시 승인과 실제 하강 결과는 final_place_run.json에 있다.

경로: `runtime/placement_reference_20260908/trial/pm02_camera_04/`. 주요 증거: result.json, final_place_run.json, final_place.log, final_state.json, after/board.jpg, entry.py, build_review.py.


## PM-02 새 C180 자세 정위치 사진 보정 재계산

사용자 ‘그럼 다시 구하면 되잖아’ 요청에 따라 기존 수동 정위치12장과 pm02_camera_04/after/board.jpg를 기판 홀로 정합하고 PM02만 재측정했다. 로봇 이동 없음. ECC12장 모두 자체 검사 통과: 보드 ΔX -1.019887mm / ΔY -0.863524mm. 현재 기판 축 기준 Base XY 진단값 [1.0329810644679858, -0.8478113685863035]mm. 기존 C0 후보를 재사용한 값이 아니다.

단, 특징점 검증은12장 중2장 합의 실패 및 분산0.728px로 거부. 외곽선 중심 검증은 ECC와 최대0.208mm 불일치/임계치별 편차0.288mm로0.15mm 기준 미통과. ECC 후보는 저장하되 교차검증 완료 보정으로 승인하거나 자동 적용하지 않는다. 독립 검증 실패 결과도 모두 보존. Z/ABC 및 기존 설정 유지, 이전 승인 런처2개 예외 외266파일해시 확인. 단일 배치 사진/부품높이 시차/실물반복성 한계 유지.

저장: `runtime/placement_reference_20260908/trial/pm02_camera_04/recalculated_reference/candidate.json`. 원본 해시·image_displacements.json·sparse_displacements.json·contour_validation.json 및 재현 스크립트 보존.


## 파워모듈4개 연속 배치 완료 — 2026-09-08

사용자 파워모듈만4개 연속 조립/중간 확인 질문 없이 진행 요청. 이후 PM02도 트레이에 복귀했다고 명시. 새 PlaceCamera 사진에서 빈 기판 확인, 새 TrayHome 관측25/25 통과 후 PM01~04만 계획. PM02는 직전 사용자 요구 C180 카메라 정방향을 실험 entry.py에만 적용, PM01 C180/PM03·04 C90 기존 방향 유지. 교차검증 미완료 수동 기준 XY 보정 후보는 적용하지 않는다고 실행 전 설명했고 기본 위치 계산 사용.

87경유점 IK 검사 통과, 최대관절구간82.746도/J6[-17.331,81.237]. Fast DDS UDPv4 실행 프로세스에서4개 연속 파지·트레이 제거검사·배치·해제·후퇴 완료. 모든 제거검사 통과, stale feedback/오류중단 없음. PlaceCamera 복귀 및 after/board.jpg에 파워모듈4개 존재 확인. 정밀 안착은 사용자 승인/계측 전이므로 확정하지 않음.

최종510개 피드백 모두정지, 그리퍼30 valid, abnormal_stop/비상/충돌/주종오류0. 기존266파일은 이전 사용자 승인 API런처2개 예외 외 해시 보존. 생산 방향설정과 전체사이클 런처 변경 없음. 현재 기판에PM4개/트레이에PM0개 상태로 취급하며 자동 반복 없음.

경로: `runtime/placement_reference_20260908/trial/pm_all_05/`. 결과 result.json, 계획 pm_plan.json, 실행 run.json/execute.log, 사진 after/board.jpg, 상태 final_state.json.


## PM4 배치 높이 추가 −0.5mm 저장 — 2026-09-08

사용자가 pm_all_05 완료 후 파워모듈 내려놓는 위치를0.5mm 더 낮추도록 요청. long_orange 레시피 board_place_z_adjustment_mm=-0.5, planner 승인값 및 executor 독립 높이검사에 반영. 런처 reviewed config hash 갱신. 파지XYZ/배치XYABC/그리퍼/다른부품 설정 유지. 공통+0.3mm는 유지하므로 PM의 calibrated Z 대비 합계−0.2mm, 직전 실제 배치 대비−0.5mm이다.

같은 pm_all_05 관측에서4개 배치Z만 정확히−0.5mm 및 보정메타데이터 변경 확인, 모든 다른 항목 동일. 이전0mm 높이 계획 거부와 런처 설치해시 통과. 기존 테스트98개 통과(기존 기대높이 검사를 새 승인값으로 갱신). 무동작 설정 작업이며 새 낮은 높이 물리실행은 아직 없음.

기록/이전 파일 백업: runtime/placement_reference_20260908/trial/pm_height_minus05/. audit.json에 동일 관측 비교, changed_file_sha256.json에 승인 변경해시. 이전 실험 baseline266해시 검사는 이번 명시 승인 변경을 반영하기 전 그대로 실행하면 실패하는 것이 정상이며 검사를 무시하지 말 것. PM02 C180은 여전히 실험 entry.py override로 보존되고 생산 성공방향파일은 이번에 변경하지 않음. 다음 PM 연속 실험은 새 촬영/계획으로 이 방향을 유지해야 함. 현재 기판에PM4개, 자동 재실행 없음.


## PM4 유지 후 SMD5 연속 배치 완료 — 2026-09-08

사용자 ‘이제 smd5개 다 놓아보자’ 승인. 새 PlaceCamera 기판 관측/사진에서PM4개 및 SMD목적지 비어있음 확인. TrayHome 새 SMD5개만 관측(capture_tray only_part_type), SMDView 근접24프레임 첫 시도에5개 전체 품질 통과. 기존 높이 CAP01−1.9mm/CAP02~05−2.4mm, 공통+0.3mm와 성공방향 유지. PM추가−0.5mm는 앞선 설정 작업이며 이 실행에서PM은 다시 움직이지 않음.

91경유점 제어기 IK 검사통과(maxstep41.775도/J6[-4.439,98.786]). Fast DDS UDPv4로 CAP01~05 연속파지/배치/그리퍼17해제/후퇴 모두 완료, 중간오류/피드백지연정지 없음. PlaceCamera 복귀 사진에서 SMD5개와PM4개 존재 확인. 실물정밀안착승인/치수검증은 미완료로 기록. 마지막419개피드백 모두정지/그리퍼17 valid/abnormal_stop·비상·충돌·주종오류0. 생산설정변경 없음, 자동재실행 없음.

경로 runtime/assembly_cycles/smd5_after_pm_20260908/. result.json, run.json, execute.log, smd_close.json, smd_plan.json, after/board.jpg, final_state.json 보존. 현재 기판PM4+SMD5/해당트레이셀이 빈 상태로 취급.


## SMD1번만 배치 높이 +0.2mm 저장 — 2026-09-08

SMD5개 실행 완료 후 사용자1번만0.2mm 위로 놓도록 요청. CAP01 슬롯 높이 override −1.9→−1.7mm, CAP02~05−2.4mm 유지. 공통+0.3mm 및 PM−0.5mm 유지. 기존 SMD default−1.9는 유지하되 승인된5개 슬롯 override를 반드시 사용하도록 기존검사 유지. planner/executor 독립 승인값·기존테스트 기대값·런처설정해시 갱신.

직전 smd5_after_pm_20260908 동일관측 비교에서CAP01 배치Z만84.834363→85.034363(+0.2mm), CAP02~05 전체값과 모든 파지XYZ/배치XYABC/그리퍼 불변. 이전CAP01높이 계획 거부, 런처설치검사 및98tests 통과. 설정 저장만 수행했고 새 높이 실기이동 없음. 현재PlaceCamera빈그리퍼17, 기판PM4+SMD5 상태 유지.

기록/백업 runtime/assembly_cycles/smd1_raise02_20260908/: audit.json, audit.py, changed_file_sha256.json, before/. 다음 실행은새촬영/계획필요.


## HBM8 연속 배치 사용자 성공 수용 및 추가−0.5mm 재시험 준비

hbm8_after_pm_smd_20260908: 새 기판/HBM8개3연속관측/169경유점IK(maxstep94.047/J6[-14.896,-4.689]) 통과 후 HBM01~08 모두 파지제거검사/배치/해제/후퇴 완료. Fast DDS UDPv4, stale feedback 중단 없음. 첫 촬영복귀는 camera_route의 C보정<-1도시360도추가 분기로 J6구간300.984도 계획이 생성되어 이동전 기존95도검사에 차단. 사용자 승인 범위 내 실험 return_camera.py로 불필요360추가만 제거하고 모든 기존IK/관절검사 유지. 정상5경유점/maxstep23.377/J6[-12.717,-8.645] 복귀/사진촬영 완료. 생산 camera_route 변경 없음.

최종사진검토/상태수집 중 사용자가 ‘다시 갖다놓아서 없을거야, 지금 좋았어 아주’라고 중단/피드백. 사진부재를미파지로판정금지. 직전결과 result.json에사용자수용기록. 복귀전511개모두정지/오류0/그리퍼25확인;복귀후추가상태수집은중단됨.

사용자가 HBM놓는값0.5더내려놓는재시험요청. HBM8 레시피board_place_z_adjustment_mm=-0.5 및planner/executor독립승인값/테스트/런처해시갱신. 같은직전관측에서8배치Z만−0.5,다른항목전부동일/이전높이계획거부/설치검사/98tests통과. PM−0.5/SMD1−1.7/SMD2~5−2.4유지. 새 hbm8_minus05_20260908 실행폴더와before백업/audit.json저장. 새PlaceCamera촬영부터재시험진행중이며 완료는아직아님. 과거좌표재사용금지.


## HBM 정위치 새 기준 저장 / 높이 총−1.0mm / 실제XY 보정 미완료

사용자는 HBM−0.5시험 뒤 ‘좋은 것 같지만 정확하지 않아’라고 평가하고 추가0.5mm하강과PlaceCamera수동정위치기준재현을요청. ‘어 정위치로 맞췄어’확인후 로봇명령없이 RGB/깊이/자세동기12장 저장. 현재기판에수동정위치HBM8+PM4+SMD5가있고자동재실행금지.

직전 hbm8_minus05_20260908은169경유점/maxstep93.356/J6[-14.845,-4.689],HBM8제거검사/배치/해제/복귀모두완료. 최종511개정지/그리퍼25/오류0. 사용자가접근해after/board.jpg대부분사람에게가림. 이를이용한직전실제오차측정불가,수동사진을자동배치성공증거로혼동금지.

HBM레시피높이−0.5→−1.0,planner/executor독립승인값/테스트/런처해시반영. 동일직전관측8개배치Z만추가−0.5/나머지항목동일/이전높이거부/설치검사/98tests통과. 새로운총−1.0실기실행없음. PM−0.5/SMD1−1.7/SMD2~5−2.4유지.

정위치직접외곽선중심측정은1~3번만반복성후보,4~8번경계/분산/약한외곽으로보류. 이것은부품높이시차가남은기판평면투영이며로봇보정값으로승인하지않음. 초기사람가림ECC실패및좁은탐색/직렬화실패진단후적분합탐색으로재측정. 독립절대중심추출은불충분하므로사진대사진비교를사용할준비완료.

compare_outcome.py는새로운가림없는자동배치사진과기준12장을기판홀정합/ECC/양방향특징점으로교차검사. 실패값을0이나실행값으로대체하지않음. 동일기준사진검사8개전부통과/가짜이동최대0.006267mm(<0.05). 이는도구자기일관성이고실물정확도검증아님. 아직실제로승인된새XY보정0개.

다음은사용자HBM8트레이복귀확인→새기판/트레이관측과총−1.0계획/IK→실행→사람이접근하기전가림없는PlaceCamera사진확보→compare_outcome.py교차검증→검증된XY만별도시험. 이전오래된계획재사용금지. 모든파일 runtime/placement_reference_hbm_20260908/: reference/, result.json, candidate/manual_centers.json, compare_outcome.py, validation_same_reference/, audit.json, height_before/.


## HBM8 총−1.0mm 재배치 완료 / 정위치 보정 교차검증 보류

사용자 트레이 복귀 및 재실행 승인 후 새 관측으로 HBM01~08 계획, 169경유점 IK 통과(maxstep93.633도). 총높이보정−1.0mm로8개 파지·트레이제거검사·배치·해제·후퇴 완료. 새 수동정위치 XY 보정은 아직 검증되지 않아 적용하지 않았음을 실행 전 설명. UDPv4 사용, 실험 짧은회전 복귀로 PlaceCamera 도착. 최종510개 피드백 모두정지/그리퍼25/비상·충돌·오류0.

가림 없는 after/board.jpg 확보, HBM8 및 기존 PM4/SMD5 확인. 수동정위치12장과 ECC/양방향특징점 비교 완료. 교차검증 통과0/8: HBM02는 ECC 자체 통과하지만 두방법 각도차1.320도, 나머지는 ECC 반복성/상관/역방향오차 또는 특징점 검사 등 실패. 계산 후보를 실측오차나 실행보정으로 확정하지 않음. 정밀정위치재현 완료 아님. 현재 HBM8은 기판에 있으며 새관측 없이 반복실행 금지.

실행: runtime/assembly_cycles/hbm8_reference_trial_20260908/{run.json,result.json,after/board.jpg,final_state.json}. 비교: runtime/placement_reference_hbm_20260908/comparison_trial1/comparison.json. 기준 result.json 업데이트. 다음 작업은 영상정합 불일치 원인 확인 및 검증된 보정 산출이며 생산XY/ABC 변경 없음.


## 2026-09-08 전체 사이클 런처 통합

아침 실행 `runtime/assembly_cycles/20260908-102057-579195`의 동일 snapshot으로 일반20개와 SMD5개를 재계산하여 비교했다. 오프라인 비교 계획은 오래된 관측이며 실행용이 아니다.

- HBM8: 아침 대비 배치Z −1.0mm. 이 높이로 8개 실제 배치 완료, 수동정위치 정밀재현 검증은 보류.
- PM4: 아침 대비 배치Z −0.5mm. 새 낮은 높이 실제시험은 아직 없음.
- PM02: 파지 C90 유지, 배치 C0→C180 카메라 정방향. pm_all_05에서 사용자가 요청한 방향으로 실기완료한 분기를 공용 방향표에 반영. planner/executor의 반대방향 거부 유지.
- CAP01: 아침 대비 +0.2mm, 슬롯 보정 −1.7mm. CAP02~05 −2.4mm 유지. 새 CAP01 높이 실기시험은 아직 없음.
- Fast DDS: shell 및 직접 Python 런처의 자식 프로세스 모두 UDPv4 사용. SHM discovery 지연을 피한 실기시험 설정 반영. 실행 중인 스택 재시작 없음.
- PlaceCamera 복귀: −1도보다 큰 음의 yaw 보정 때 360도를 더하던 분기 제거. 실험에서 사용한 짧은 복귀를 정식 코드에 반영. 안전Z/관절별95도/J6/IK 검사 유지.
- GPU/VRM/IND 및 나머지 CAP의 좌표·그리퍼 값 보존. 모든 파지 좌표와 배치XY 불변. PM02 roll ±180 표기는 같은 자세이며 실제 회전 추가가 아니다.

요청한 변경만 나타남을 항목별 assert로 확인하고 독립 executor 계획검사 및 런처 설치해시 통과. 관련 테스트162개 통과, dry-run 통과. 통합 후 전체25개 실제 재실행은 하지 않았다. 다음 실제 실행은 기존 명령 `./run_fr5_cycle.sh --execute`로 새 촬영과 IK 검사를 거친다.

HBM 도착 비교: XY 0.018~0.193mm, 도착판정 시점 Z 목표보다 +0.264~+0.552mm(평균+0.398mm), C 최대 약0.0011도. 해제직전 정착좌표 또는 실물부품 오차를 뜻하지 않으므로 이를 추가 하강 보정으로 적용하지 않음. 원본 `runtime/assembly_cycles/hbm8_reference_trial_20260908/arrival_comparison.json`.

미검증 수동정위치 XY/각도 후보는 실행에 반영하지 않음. HBM사진 교차검증0/8 통과, 정밀재현 미완료. 이번 코드통합은 전체 정밀안착 성공을 뜻하지 않음.

파일: before/ 이전7파일 백업, morning_comparison.json 전체 항목변경·해시·검증, non-smd_offline_plan.json 및 smd_offline_plan.json 비교 전용.

최종 `./run_fr5_cycle.sh --check` exit0: 로봇/Tool1/티칭점/D435 준비 확인, AUTO0/User0/그리퍼25/오류0. 이동 및 그리퍼 명령 없음.


## 전체 사이클 ROS API 배포 및 Unity 전달물 — 2026-09-08

사용자 Sequencer YAML 최신화/내부 실기코드 API화/Unity동기화 요청. 기존 개별 robot.pick/place 경로는 전체 실기런처와 달라 같은 성공보장 불가 확인. 선택질문 응답 없이 설명한 기본안대로 검증된 전체25 런처를 호출하는 /real/assembly/command(start/stop), /event, /state, /robot_state, Trigger /status 추가. 순서는 기존GPU/HBM/PM/VRM/IND/SMD 유지. 최신 참고 YAML은 사용자 HBM/PM/GPU/CAP/IND/VRM순서 유지하되 실기흐름검증 완료로 표기하지 않음.

현재 그리퍼 진입/파지/해제: HBM25/18/25, PM30/25/30, GPU70/65/70, CAP18/12/17, IND21/14/20, VRM30/24/28. recipe.current.yaml은 참고본, 런처는 기존실기레시피/방향/높이 그대로 사용. Home복사 준비점/완성PCB이송/컨베이어·검사 외부handler 미완료 구분.

UUID/현재revision/명시적scene-ready 확인, 임의TCP/파일명 차단, 영속요청기록·동일요청재전송시상태만반환, API재시작미해결시recovery_required, 중단은런처SIGINT→기존StopMotion처리. 개별API와전체런처공통flock, 잠금거절시소유자에게StopMotion금지. 실제 관절10Hz·진행2Hz. 완료는motion_complete_awaiting_physical_verification이고정밀안착PASS가아님.

Unity AssemblyCycleClient.cs 및 AssemblyMeasuredRobotSynchronizer.cs 추가. 실제모델관절할당/기존부호영점필요, 자동시작없음, 실측피드백과Ghost분리. Unity Editor컴파일/외부씬연결미실시.

관련233tests통과, colcon선택패키지build통과, 설치4개핵심Python소스일치검증. 511개정지/held없음확인후로봇API만재시작(드라이버/카메라유지). 실제새/real/assembly/status idle/enabledtrue, 상태16개/실측83개수신·모두정지, confirm_scene_readyfalse요청INVALID_REQUEST거부/실행폴더생성없음. 실제이동명령없음. 기존런처dry-run통과. API를통한25개실기실행은아직없음.

기록 runtime/assembly_api_integration_20260908/{before/,result.json,live_check.json,check_api.py}. 사용문서 docs/ASSEMBLY_CYCLE_API_KO.md. 운영서버재시작후문제가생기면 runtime/assembly_stack/logs/robot_api.log 최신기동시각 이후를확인(이전프로세스종료중rclpytraceback은새기동이전기록). 복구필요상태를자동삭제하여재실행하지말것.


## 런처·부품그룹 시험 API 공통 진입점 전환 — 2026-09-08

사용자 ‘런처나테스트도API로돌리는거지’질문에아직직접실행경로남았다고설명후‘어그렇게’로전환승인.
run_fr5_cycle.sh는 이제 assembly_api_client.py를 호출하는 공개 API클라이언트. API 내부는 scripts/run_assembly_cycle_worker.sh→기존assembly_cycle_launcher.py를호출하여재귀없음. API불통시직접실행우회없음. default/--dry-run/--status는API조회, --check는assembly.check(무동작), --execute는assembly.start. Ctrl+C/--stop은해당작업API중단요청이고정지완료와구분.

--execute --part GPU/HBM/PM/VRM/IND/SMD로해당종류전체시험. 공개API profile은고정목록만허용, 임의스크립트/과거plan인수없음. whole-group capture에기존TRACKING/Base/handeye/품질/고유1..N/신선도/카메라정지4프레임검사유지. 그룹계획은기존build_plan/validate_plan/IK/executor/그리퍼/성공방향그대로사용. VRM만추가정밀측정, SMD는필수근접측정, 일반부품은TrayHome파지제거검사, 마지막카메라복귀사진. 기존전체순서불변. 과거runtime시험스크립트는이력으로보존하며이후시험진입점으로사용하지않음.

274tests통과. 같은아침관측의6개그룹순수계획을최신전체계획과대조하여모든item필드동일확인. 과거관측을실제그룹builder에넣은첫시도는stale로거부됐고검사유지/시각갱신없음. 이오프라인계획은실행금지.

유휴API/로봇정지확인후API만재배포. 공개 ./run_fr5_cycle.sh --check가API요청e8c575cb-c20a-417d-9fa7-6f5bfa22b146→내부worker→check_completed/exit0까지완료. 서버로그motion_sentfalse/무그리퍼명령확인. Unity/CLI동일상태경로. 새그룹/전체물리실행은하지않음. Unity스크립트는check_completed이후시작허용및선택profile추가, 외부씬연결/컴파일미검증.

기록runtime/api_entrypoints_20260908/{before/,result.json,group_plan_audit.json}. API/클라이언트요청기록runtime/assembly_api/,runtime/assembly_api_clients/. 사용문서docs/ASSEMBLY_CYCLE_API_KO.md. Unity전달zip최신화.


## API 첫 전체 사이클 GPU 미파지로 사용자 중단 — 2026-09-08

사용자 기판/트레이25개/빈그리퍼/작업영역 준비 확인 후 API --check 통과, --execute로 d9abe11d-0586-4df3-8fd3-89e1ddd875dc 시작. 새25관측/VRM정밀측정/일반20IK통과 후GPU파지시도, TrayHome제거검사 대기 중 사용자 ‘GPU 못 잡았는데’ 보고. 즉시 API assembly.stop, stopped_on_error/recovery_required. 완료슬롯0, grasp_verified0. 피드백개도65나 내부held_candidate를실제파지로간주금지. 다음부품/기판배치없음.

최종505개모두정지, gripper65/abnormal_stop1(StopMotion후)/비상·충돌·주종오류0. 자동reset/재시작없음. GPU개도70/65/70 및XY보정0은아침과동일. 새파지TCP[-517.706,-190.447,-47.678,-180,0,89.748],아침[-517.064,-184.201,-49.719,-180,0,90.588]. XYZ차[-.642,-6.246,+2.041]은재배치/측정차이를구분하기전실측오차로확정금지. 사용자실제현상확인대기. 기록해당실행폴더 operator_failure.json/stopped_state.json/non-smd_run.json 및API기록.


## 사용자 직접 전체 재실행 준비 복구
사용자 직접전체실행의사와기판/그리퍼/영역비움·25트레이복귀확인. API유휴/실행잠금확보후API만종료, 기타안전오류없음확인후ResetAllError. 직후검사는과거큐상태로실패했으나별도새구독189개모두정지/abnormal_stop0/오류0검증. 실패원기록보존하고API기록에recovered_after_operator_scene_reset및현장확인증거추가(삭제/실패성공변환없음). API재연결후공개--check fa82f0c5-ef48-4774-bb1f-c42537e591c7 check_completed exit0. 실제조립시작/그리퍼명령없음. GPU미파지원인미해결,사용자가직접--execute시작예정. 증거 runtime/gpu_stop_recovery_20260908/recovery.json.


## 콜백 검증 PM 높이 설명 정정 — 2026-09-08

PM-03/04 테스트의 -0.5mm 차이는 사용자 승인한 PM 추가 하강이 저장되지 않은 문제가 아니다. 현재 레시피와 runtime/gpu_fixed_pick_z_20260908 백업 모두 long_orange board_place_z_adjustment_mm=-0.5다. 9/7 실측 fixture를 직접 비교하던 테스트만 9/8 승인값을 반영하지 않았다. 원본 fixture는 보존하고 기대 Z에 승인된 -0.5mm를 적용하여 전체 로봇 패키지+vision 테스트 595개 통과. 실제 설정/로봇 동작/서비스 상태 변경 없음.


## 사이클 속도 개선 1단계 — 2026-09-08

사용자 승인으로 planner/executor 속도 계약에 high_transfer=30, clearance_lift=25 추가. tray_after_raise는 10→25, 높은 위치의 pick/place/tray 이동은25→30. 기존 travel25/combined_rotation25/vertical10 및 전역40 유지. 파지·배치 마지막50mm/최초후퇴50mm/트레이홈검사 진입속도10 유지. 카메라·복구처럼 새키를 명시하지 않은 호출자는 기존속도 그대로. 구속도 계획은 executor 계약 검사로 거부하며 새 계획 필요. 전체598tests통과, 기존 일반20 계획은 속도와 생성시각 외 동일. 블렌딩/중간점 삭제는 미구현, 실기속도시험 없음. 로봇은 TrayHome, API 꺼짐 및 정지래치/IND실패기록 보존 상태. 자료 runtime/cycle_speed_stage1_20260908/validation.json.


## 구간 속도 40/30/10 사용자 확정 — 2026-09-08

사용자가 높은 위치 이동·회전40 / 긴 상승30 / 파지·배치 근처10, 전체40%유지를 명시 확인. planner 및 executor 속도계약 high_transfer=40, clearance_lift=30, vertical=10으로 저장. 나머지 travel25/combined_rotation25 유지. 전체598tests통과. 로봇 이동·서비스 재시작·실기 속도시험 없음. 이전1단계30/25값을 대체하며 새계획 생성 필요. runtime/cycle_speed_stage2_20260908/validation.json에 기록.


## 연속 이동 코드 구현 — 2026-09-08

사용자가 속도 시험보다 중간점 정지 개선을 우선 요청. API precision Pick/Place의 높은 위치 MoveJ 2~3점을 CONTINUOUS_TRANSFER로 묶고 중간blend50ms/끝점0ms·최종대기1회 구현. 명령별blendT 드라이버 확장 및 기능버전 확인. 실패시StopMotion/복구유지·자동재전송없음. 전체604tests통과. 기본비활성, 실제이동/서비스재시작없음. retained resume와 동시사용거절. 실기경로/취소정지 검증 및 활성화는 남음. docs/CONTINUOUS_TRANSFER_20260908.md 참고.


## 연속 이동 실제 서비스 활성화 — 2026-09-08

사용자가 연속 이동도 적용하도록 명시 요청. config/ksmc.env KSMC_CONTINUOUS_TRANSFER=true 및 API 시작 파라미터 연결. 드라이버 재시작으로 per-command-blend-v1 확인, API continuous_transfer_enabled=true 확인. --check 최종통과, 정지/유휴/복구없음. 종료돼 있던 tray_vision 재연결. 로봇 저장소 scripts/run_fairino_endpoint.sh에서 기존 외부 래퍼의 1초 CLI 준비 대기를6초로 보완, 기존 endpoint 소스/Unity브랜치 수정없음. 실제 조립/그리퍼/이동시험은 실행하지 않음. runtime/continuous_transfer_activation_20260908/launcher_check_final.log 참고.

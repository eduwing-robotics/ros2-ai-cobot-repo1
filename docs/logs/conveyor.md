# Conveyor Work Log

## 2026-09-11 GoPro included in the ROS server bundle

GoPro now starts with the conveyor/inspection bundle unless disabled, while an
existing GoPro remains externally owned. A failed newly owned GoPro process uses
the existing peer-shutdown path; no conveyor motion/stop criteria or Endpoint
were changed and no motor command was sent. Tests and remaining live startup /
remote-viewer checks are in [the grouped vision log](vision.md#2026-09-11-gopro-bundle-lifecycle-and-remote-rqt-diagnostics).

## 2026-09-11 ROS-only conveyor and inspection bundle

The integrated launcher now starts ROS inspection services alongside the existing
ROS conveyor controller and verifies typed server discovery. Conveyor motion,
stop, arrival and timeout rules are unchanged; capture still requires an explicit
Sequencer request. No robot/conveyor command or teammate Endpoint action was sent.
Software and isolated DDS validation, migration scope and remaining live-system
checks are recorded once in [the grouped vision log](vision.md#2026-09-11-ros-only-inspection-request-and-result-transport).

## 2026-09-11 — Prevent duplicate HQ teardown and restore persistent services

- The 11:56 KST failure was traced to the one-command cell, not ROS domain
  selection. The existing S22 process was running as `bash
  ./run_s22_conveyor_hq.sh`, while `run_conveyor_cell.sh` only recognised an
  absolute script spelling. The cell therefore started a second HQ. Its
  startup `pkill` removed the first HQ's ROI; the first HQ then cleaned up the
  shared camera, the second HQ failed its camera gate, and the cell stopped the
  conveyor server. The server log had only its startup line at 11:56:08 KST;
  the S22 camera log ended at 11:56:10 KST, matching this teardown sequence.
- `run_conveyor_cell.sh` now resolves each `/proc/<pid>/cmdline` script
  argument before matching, so absolute, relative and `./` invocations reuse
  the same HQ. `run_s22_conveyor_hq.sh` now holds an exclusive HQ launcher
  lock before stale-ROI cleanup. A race that loses this lock is treated as a
  reuse case and no longer tears down an already-running server. Normal ROS
  shutdown also handles `ExternalShutdownException` without a false traceback.
- Validation: shell syntax passed; `vision_server` rebuilt successfully. A
  monitor-only 24-second cell run reused an existing HQ and stayed alive. A
  detached, armed integrated run using `setsid
  ./run_conveyor_vision_server.sh --execute --confirm-motion` is currently
  alive with ROS domain 5: `/conveyor/move_to_assembly`,
  `/conveyor/move_to_inspection` and `/conveyor/stop` each have one local
  provider, `/conveyor/state` has one publisher, and `0.0.0.0:8766` accepts
  connections (an unauthenticated probe correctly returned HTTP 401). S22
  and ROI remained a single external HQ process throughout the replacement.
- No move service, inspection request, positive `/cmd_vel`, robot, Job, DB or
  Sequencer command was issued. Server startup is armed but begins in IDLE and
  emitted no nonzero command. During the earlier replacement check a separate
  `turtlebot3_teleop` `/cmd_vel` publisher was present; the remote server
  intentionally rejects a move while that second command owner is present.
  The final live check has one server publisher and one TurtleBot subscriber.

## 2026-09-11 Add one-command cell launcher and preserve Wi-Fi SSH

- Added `run_conveyor_cell.sh` and the additive
  `run_conveyor_remote_server.sh --with-s22` form. It starts the conveyor
  remote server first, then starts or reuses `run_s22_conveyor_hq.sh`, supervises
  only processes it owns, and refuses to touch the camera when the existing
  `/cmd_vel` owner lock is held. It never starts the Unity ROS-TCP Endpoint or
  the GoPro launcher; those remain separate team-managed processes.
- The laptop currently has `enp129s0=10.77.5.1/30` and Wi-Fi
  `wlo1=192.168.11.4/24` with the Wi-Fi default route. A read-only SSH probe to
  `musk@192.168.11.101` reached the robot but was rejected with
  `Permission denied (publickey,password)`, so no robot network setting was
  changed. The documented robot-side additive profile uses
  `10.77.5.2/30`, no Ethernet default gateway, and leaves Wi-Fi/SSH enabled.
  An opt-in `config/fastdds_laptop_wired.xml` is available for the later ROS
  switchover; it is not active until both robot and laptop wired paths are
  verified.
- Validation: `bash -n` passed for both launchers and `run_conveyor_cell.sh
  --help` completed without starting ROS, cameras, endpoint, or motion. No
  robot, conveyor, Job, DB, Sequencer, or Unity command was issued for this
  change. Physical wired reachability and ROS subscriber migration remain
  pending authorized robot-console/SSH access.

## 2026-09-11 Prevent competing conveyor command owners from causing belt jerk

- Read-only host inspection found two `conveyor_remote_server` processes alive
  in ROS domain 5 at the same time (PIDs 22175 and 24490 under separate
  launchers). The graph collapsed the identical node names and showed only one
  visible publisher, so process ownership must be checked in addition to
  `ros2 topic info`. The direct `run_conveyor_to_assembly.sh` path also owns
  `/cmd_vel`; running it beside the service server can alternate its `-0.10`
  command with the server's zero command and make the physical belt jerk.
- The standard remote-server launcher and direct one-shot wrapper now share
  the process-lifetime `runtime/conveyor_cmd_vel_owner.lock`. A second local
  command owner is refused before it can publish. The documented operation is
  to stop the remote server before using the direct test wrapper, or use the
  remote movement service while the server owns the topic.
- Current read-only measurements after the camera/ROI restart were S22 capture
  30.0 FPS and `/camera2/image_stream/compressed` 29.2--29.9 FPS. The optional
  reliable stop overlay was only 5.3 FPS (about 80 KB per frame) while three
  subscribers were present, so a Unity stop-screen that uses this topic can
  look stuttered even while the control stream remains current. The direct
  wired interface is 1 Gb/s at `10.77.5.1`, but the robot address
  `10.77.5.2` did not answer ARP/SSH; robot ROS traffic therefore remains on
  Wi-Fi `192.168.11.101` until the robot side is configured.
- Validation: `bash -n` passed for all conveyor wrappers and an isolated
  `flock` contention check returned the expected refusal. No movement service,
  positive `/cmd_vel`, robot, Job, or Sequencer command was issued during this
  performance investigation. The stale duplicate was then retired during a
  controlled IDLE restart. The rebuilt service is the only
  `conveyor_remote_server` process, reports `IDLE/moving=false`, and emitted no
  `/cmd_vel` sample during a three-second passive-IDLE observation. A direct
  `run_conveyor_to_assembly.sh --station assembly` attempt was refused by the
  lock before ROS was invoked. No physical movement was commanded.

## 2026-09-11 Prevent remote IDLE zeros from overriding manual teleop

- Read-only host inspection found two `conveyor_remote_server` processes alive
  in ROS domain 5 at the same time (PIDs 22175 and 24490 under separate
  launchers). The graph collapsed them to one node name and showed one visible
  publisher, so process ownership must be checked in addition to
  `ros2 topic info`. The one-shot `run_conveyor_to_assembly.sh` path also owns
  `/cmd_vel`; running it beside the remote server can interleave its `-0.10`
  command with the server's zero command and make the belt jerk.
- The remote server's `_control_tick()` previously published `/cmd_vel=0.0`
  every 20 ms whenever it was not moving, including `IDLE`. That competed with
  an operator's `turtlebot3_teleop` publisher. IDLE is now passive; latched
  `ASSEMBLY_STOP`, `INSPECTION_STOP`, `MANUAL_STOP`, and `FAULT` still repeat
  zero for the stop hold, and entering/resetting those states still emits an
  immediate zero. A rejected service request also does not inject a zero when
  another `/cmd_vel` publisher owns the topic.
- The normal remote-server launcher and direct one-shot wrapper share the
  process-lifetime `runtime/conveyor_cmd_vel_owner.lock`, so a second command
  owner is refused before it can publish. The operator must leave the remote
  state in `IDLE` before starting teleop; active station holds remain a stop
  interlock and require the existing reset procedure.
- Validation: targeted remote-server regression tests passed (`81 passed`),
  including passive IDLE ticks, teleop publisher rejection without a zero
  pulse, and continued zero publication in latched stop/fault states. No
  positive `/cmd_vel` was issued during this investigation; physical teleop
  response remains to be checked after the operator selects exactly one command
  owner and confirms the TurtleBot is clear.

## 2026-09-11 Remove status heartbeat faults and reject disconnected robot moves

- The active conveyor control path no longer treats the age or absence of a
  periodic S22 `ready`/station-trigger sample as a heartbeat fault. A received
  `ready=false` still stops a move, a received stop trigger still latches the
  destination STOP state, stale camera frames are ignored for new control and
  arrival evidence, and the finite 30-second motion timeout remains the
  bounded fallback.
- The remote server now checks the resolved `/cmd_vel` graph before accepting a
  move and requires a compatible `geometry_msgs/msg/TwistStamped` subscriber.
  If TurtleBot bringup is down, the request is rejected immediately with
  `robot command receiver is not connected on /cmd_vel` instead of being
  accepted and timing out after 30 seconds. The check also faults an active
  move if its receiver disappears.
- The 2026-09-10 evidence was an accepted request at 20:29:22.936 KST followed
  by `CONVEYOR HOLD: FAULT: motion timeout` at 20:29:52.949 KST. At that
  interval ROS showed one `/cmd_vel` publisher and zero subscribers; the known
  TurtleBot address `192.168.11.101` was unreachable and the laptop wired
  interface had no carrier. Unity/Sequencer reached the server, but the robot
  command path was not available. The earlier 18:23:39 event was the separate
  stale-S22-status fault that this change removes from active control.
- Validation: all 181 offline `vision_server` tests passed, including stale
  status, explicit not-ready/trigger, receiver preflight, arrival-age and
  stale-frame cases. One guarded `/conveyor/move_to_assembly` service request
  was issued after the rebuild; it returned the receiver error and published
  no nonzero `/cmd_vel`. No reset, Job, Unit or Sequencer command was sent.
  Physical motion remains unverified until TurtleBot bringup and its network
  endpoint are restored; the software now fails closed at the service boundary
  in that condition.

## 2026-09-10 User-authorized MANUAL_STOP reset

- The live `/conveyor/state` preflight reported `MANUAL_STOP`, `moving=false`,
  with fresh S22 readiness. After confirming that the belt was not moving, the
  user-authorized `/conveyor/reset` Trigger was called once.
- The server returned `success=true`, `controller reset to IDLE; conveyor
  remains stopped`; a follow-up state read reported `IDLE`, `moving=false`.
  No move, stop, robot, Job, or Sequencer command was issued.
- Unity may now request the normal first move from `IDLE`, subject to its
  existing ready/interlock checks. The reset only clears the controller hold;
  it does not move or reposition a board.

## 2026-09-10 S22 control heartbeat separated from Unity overlay traffic

- A live ROI warning measured `control_publish=313.9 ms` while the belt was
  still upstream of assembly. The blocking portion was the non-critical
  station telemetry publication; it could starve the 150 ms S22-ready watchdog
  even though rqt showed a live image.
- Station line/detection/polygon/distance messages now use a bounded latest
  snapshot worker. The callback sends station triggers, ready, and spacing
  heartbeats first, then drops stale display telemetry when the worker is
  behind. Arrival observation and all motion interlocks remain unchanged.
- The optional stop-image topic now offers reliable depth-1 QoS to match the
  Unity ROS-TCP display while retaining compatibility with rqt. After a safe
  ROI/camera restart, 20-second read-only probes received 590 camera frames
  and 592 ready heartbeats (29.5/29.6 FPS), with no slow-callback or stale-frame
  log. `ros2 topic info` showed the rqt and team Endpoint subscriptions. No
  reset, move, robot, Job, or Sequencer command was issued.

## 2026-09-10 S22 ready heartbeat latency mitigation

- An interrupted assembly move stopped upstream of the station because the ROI rejected a 185 ms old frame and the controller latched `S22 ready heartbeat missing`; it was not an arrival stop. Deployed Fast DDS interface filtering and non-blocking UDP on the laptop, preserving the 150 ms watchdog and manual/fault behavior. Matched audit reduced ready false samples/gaps over150 ms to0; the robot Ethernet endpoint is still unconfigured, so the remote robot remains on Wi-Fi. No movement, reset, robot, Job or Sequencer request was issued. Detailed measurements and remaining physical-test limits: [grouped vision record](vision.md#2026-09-10-s22-heartbeat-latency-and-wired-transport-mitigation).
- The laptop-only DHCP probe on the connected cable found no robot lease/ARP response and was reverted to static `10.77.5.1/30`; no robot network or conveyor command was changed.
- Latest read-only preflight remains `MANUAL_STOP`/zero command with fresh ready. Unity must perform the explicit reset recovery before its next move request; pressing the process button immediately will be rejected. No reset or move was issued here. Fallback details: [heartbeat rollback note](../team_handoff/conveyor_remote_api/HEARTBEAT_ROLLBACK.md).
- After the TurtleBot power cycle, its known Wi-Fi IP is ARP-incomplete and `/cmd_vel` has zero subscribers on ROS domain5. The laptop cable is physically1Gb/s but the robot Ethernet endpoint has no address/lease. Bring up the TurtleBot on its local console or restore authorized SSH before Unity; no robot start or conveyor command was issued.

## 2026-09-10 Automatic IDLE for restart from the start area

- Deployed automatic cleanup of ASSEMBLY_STOP/INSPECTION_STOP after both station regions have positive empty-belt evidence for2s/20frames; retains manual stop/fault and existing motion guards.178 offline tests passed; live empty evidence qualified with stationary IDLE. No motion/robot/Job request; lifecycle zero commands apply. Physical interrupted-process replay remains untested. Detailed behavior, calibration and limitations: [grouped vision record](vision.md#2026-09-10-automatic-idle-after-both-station-regions-become-empty).

## 2026-09-10 Current visual arrival and safe same-destination completion

- Added fresh raw-frame arrival observations, read-only arrival queries and verified no-motion completion for repeated requests at the same stopped destination. Existing motion guards and historical trigger semantics remain.162 ROS tests and24 bundle tests passed; live read-only S22/state probe correctly abstained in the actual MANUAL_STOP state. Subsequent user-authorized ROI/bundle deployment completed; final live state IDLE/zero command with fresh vision readiness. Lifecycle stop publication applies; no move/reset/robot request or Job/DB change. Both stations currently report no board in the station window; positive physical arrival and Sequencer integration remain unverified. Detailed behavior, engineering limits, measured observations and limitations are recorded once in the [grouped vision record](vision.md#2026-09-10-current-s22-arrival-observation-and-completed-request-handling).

## 2026-09-09 Remove FR5 conveyor permission

- User-authorized bundle restart completed; live state is IDLE/zero command with FR5 permission disabled. Shutdown/startup emitted stop commands; no movement requested. Deployment evidence is in the linked grouped record below.

- Removed FR5 permission gating/subscription; S22 watchdogs and stop behavior remain. 126 offline tests passed; no live commands or restart. Checkpoint, final behavior, evidence and operational limits: [grouped vision record](vision.md#2026-09-09-remove-fr5-conveyor-permission).


## 2026-09-09 Correlated persistent arrival callbacks

- Added compatible motion_id/arrival fields and teammate callback examples; safety gates and legacy states unchanged. Current direct ROS discovery found trigger publishers but no remote-server state/services; no server was launched or motion commanded. Offline tests cover both stations, repetition, reset/fault and late consumers. Detailed shared validation and limitations: [vision record](vision.md#2026-09-09-arrival-callbacks-and-countermeasure-evidence-cards).

## 2026-09-08 inspection child UNKNOWN retry

- Inspection child now retries UNKNOWN once (max2captures), preserves attempt paths, and recommends HOLD if stillUNKNOWN. PASS/FAIL and offline skip-capture do not retry. No conveyor/robot command; actual Sequencer HOLD handling unverified. Existing API server/request IDs/routes unchanged; next child invocation uses new code and can take longer. Combined tests302passed without hardware. Detailed grouped record: [vision log](vision.md#2026-09-08-bounded-unknown-recapture-pipeline).

## 2026-09-08 freshness and duplicate-request hardening

- Invalid/stale image and heartbeat evidence now inhibits readiness; ready-loss and invalid motion clocks latch stop, while same-active-request retries preserve the original deadline without a stop/restart pulse. Existing geometry/speed/interlocks/topic contracts unchanged.123offline ROS-package tests passed; no publishers, equipment commands or live-server restart. See [grouped behavior and verification](vision.md#2026-09-08-parallel-subsystem-hardening-and-offline-regression-runner); physical stopping and cross-PC timestamp consistency still require operational verification.

## 2026-09-08 additive conveyor and inspection server supervision

- Added an opt-in shared launcher with duplicate/takeover refusal and owned-process-only cleanup; existing conveyor services, safety interlocks, station geometry and request-owned capture behavior are unchanged. Actual-host read-only preflight passed; no conveyor server was started or motor command sent. Mock lifecycle/API tests and existing interlock regression tests passed. See [grouped implementation and verification record](vision.md#2026-09-08-non-disruptive-server-bundle-and-recorded-result-viewer) for details and the still-required idle switchover/teammate live test.

## 2026-09-07 request-owned inspection trigger

- Default run_conveyor_inspection_trigger.sh now serves Sequencer request/pull API rather than firing on arrival. Existing arrival behavior is explicitly --legacy-arrival-trigger only; both use the same process lock. Combined S22 launcher help/token preflight updated. Fresh stopped and arrived messages are prerequisites; arriving without POST does not capture. Automatic direct MainServer delivery removed, evidence pulled by Sequencer. Stop geometry, motor/interlock code unchanged.20 API/export/pipeline tests and shell syntax passed; no physical motion/capture or end-to-end ROS test. See grouped vision log for deployment limitations.

## 2026-09-07 automatic inspection result file delivery

- Arrival-trigger child pipeline now uses existing hybrid25-slot inspector rather than legacy full-board default. Optional file export/HTTP receipt is off by default; completion and delivery states remain separate. No stop geometry, motor command, interlock, rearm policy or conveyor remote server change. Local mocked pipeline tests and HTTP loopback tests passed; physical arrival/capture/inspection/upload sequence not executed. See vision.md grouped MainServer file-only receipt record for details and limitations.

컨베이어 모터·정지 제어 변경만 기록한다. S22 영상 알고리즘은 `vision.md`, FR5
작업은 `robot.md`에서 관리한다.

## 2026-08-20 — 조립 정지와 비전검사 정지를 2단계로 분리

- 한 실행에서 사용할 station을 `assembly` 또는 `inspection`으로 명시하도록
  `conveyor_controller`에 `--station` 옵션을 추가했다.
- 실행 명령을 `run_conveyor_to_assembly.sh`와
  `run_conveyor_to_inspection.sh`로 분리했다. 첫 정지 후 FR5 조립 완료·후퇴를
  확인하지 않은 상태에서 검사선으로 자동 재출발하지 않는다.
- 실제 벨트 전진은 기존 검증값인 TurtleBot `linear.x=-0.10 m/s`를 유지한다.
- 기존 ready heartbeat뿐 아니라 선택한 station trigger 토픽도 1초 watchdog으로
  감시한다. 시작 후 3초 안에 둘 중 하나라도 수신되지 않거나 실행 중 끊기면 속도
  0을 10회 발행하고 종료한다.
- 소프트웨어 검증까지만 수행했으며 이번 변경으로 실제 바퀴·벨트를 구동하지
  않았다. 최종 컨베이어와 S22 고정 후 조립선, 검사선 순서로 각각 저속 실물 정지
  시험을 해야 한다.

### 발표·포트폴리오용 증빙 항목

- S22 화면에 두 정지선과 기판 2장이 동시에 표시된 캡처
- 조립선 trigger와 검사선 trigger가 서로 독립적으로 발생하는 터미널 로그
- 기판 길이보다 정지선 간격이 좁을 때 `station_spacing_valid=false`로 정지하는 로그
- 조립 완료 확인 후에만 두 번째 이동 명령을 실행하는 공정 순서 영상

## 2026-08-20 — 최종 S22 시점의 2개 정지선 재측정

- 현재 고정된 비스듬한 S22 화면에서 빈 기판 지그와 완성 기판 지그를 동시에
  측정했다.
- 지그 손잡이가 기판 중심을 위쪽으로 치우치게 하던 문제를 해결하기 위해 넓은
  본체 단면만 추출하는 검출 로직을 추가했다.
- 1920px 영상 기준 본체 후단은 조립 위치 약 `565.94px`, 검사 위치
  `1344.00px`였고 정규화 정지선은 `0.29491513`, `0.70036477`로 설정했다.
- 두 정지선을 각각 실측하여 S22 원근 왜곡을 반영했다. 실제 벨트 상판 완성 후
  같은 절차로 최종 미세조정한다.
- Vision 테스트 `21 passed`, ROS 패키지 빌드 성공을 확인했으며 실제 컨베이어는
  움직이지 않았다.
- S22 고정 화면에서 TurtleBot 몸체·삼각대·테이블 물체가 간헐적으로 기판으로
  검출되는 문제를 막기 위해 검출 범위를 컨베이어 벨트 띠 `Y=0.42~0.76`으로
  제한했다. 기판 형상 조건도 aspect ratio `1.25~1.90`, rectangularity
  `>=0.78`로 강화했다.
- 최신 S22 실물 프레임에서는 빈 기판과 완성 기판 2개만 유지됐고, 벨트 밖의
  TurtleBot형 어두운 사각 물체를 제외하는 회귀 테스트를 추가했다. Vision 전체
  테스트는 `22 passed`이며 실제 모터는 구동하지 않았다.

## 2026-08-21 - 회전 PCB의 지그 손잡이 제외 보정

- 실제 S22 오버레이에서 PCB가 약간 회전하면 기존 박스가 지그 손잡이까지
  포함하는 문제를 재확인했다. `body_span_ratio`만 조정하는 방식은 손잡이가
  본체 외곽을 넓히는 경우에 충분하지 않았다.
- `fit_dominant_body_box()`를 양축 scan-line profile 방식으로 수정했다. 본체
  폭의 중앙값을 기준으로 두 축을 모두 검사하고, 중앙값보다 큰 돌출 폭이
  전체 profile의 소수 구간에 반복될 때만 해당 축의 경계를 본체 경계로
  보정한다.
- 따라서 PCB가 90° 회전해 손잡이가 다른 축으로 돌출되어도 본체 중심과
  본체 사각형을 기준으로 표시한다. 방향 자체는 계속 `HORIZONTAL`,
  `VERTICAL`, `ROTATED`로 표시하며 검출을 중단하지 않는다.
- 현재 S22 프레임 오프라인 결과: 왼쪽 본체 중심 약 `(582.6, 484.3)px`,
  본체 박스 장축 길이 약 `235.5px`; 손잡이를 포함한 중심 약 `596px`에서
  본체 쪽으로 보정됐다.
- 90° 회전 손잡이 회귀 테스트를 추가해 Vision 테스트 `23 passed`를 확인하고
  `vision_interfaces`, `vision_server`를 다시 빌드했다. 실행 중인 S22/ROI
  노드는 재시작해야 새 검출 로직이 적용된다.
## 2026-08-20 - S22 Wi-Fi 정지 응답 개선

- S22 Wi-Fi 영상은 USB 경로보다 정지선 반응이 양호함을 확인했다.
- 정지 판정은 `stable_crossing_frames: 1`로 유지한다.
- `/vision/conveyor/{station}/stop_trigger=True` 수신 즉시 `/cmd_vel`에 0을 발행하도록 컨베이어 제어기를 수정했다.
- 기존 50 ms 제어 타이머는 반복 정지 명령과 heartbeat 안전 감시용으로 유지한다.
- `vision_server`를 다시 빌드했고 단위 테스트 22개가 모두 통과했다.
## 2026-08-21 - 수평 S22 재설치 후 ROI·정지선 재보정

- S22를 수평 방향으로 재설치한 현재 1920×1080 프레임을 확인했다.
- 기존 `search_y_start=0.42`가 기판 상단을 잘라 검출을 막고 있었고,
  `min_area_fraction=0.03`도 현재 기판 면적보다 높았다.
- 새 설정: 검색 Y `0.25~0.68`, 최소 면적 비율 `0.018`.
- 현재 프레임 오프라인 검증 결과 기판 2개를 정상 검출했다.
- 조립 정지선: `x=442 px`, normalized `0.23020833`.
- 검사 정지선: `x=1104 px`, normalized `0.57500000`.
- 두 정지선은 현재 화면에서 각각 왼쪽 빈 기판과 오른쪽 조립 기판의
  trailing edge에 맞췄다.
- 새 설정 반영을 위해 `vision_server`를 재빌드했다. 실행 중인 S22/ROI 노드는
  종료 후 다시 시작해야 한다.
- 기판 장축 각도를 계산해 `HORIZONTAL`, `VERTICAL`, `ROTATED`로 오버레이에
  표시하며, 방향이 달라도 검출을 폐기하지 않도록 했다.
- 0°, 30°, 90° 합성 기판 검출 검증을 통과했다.
- 90도 회전 시 지그 손잡이가 박스에 포함될 가능성을 줄이기 위해 본체
  cross-section 기준을 `body_span_ratio=0.85`로 강화했다.

## 2026-08-21 - 조립 기판 손잡이 돌출 기준 추가 조정

- 저장된 실제 조립 기판 프레임의 프로파일을 다시 측정했다. 조립 기판의
  손잡이 돌출 구간은 전체 프로파일의 약 `16.6%`였고, 기존 기준 `0.20`은
  이 구간을 손잡이로 확정하지 못했다.
- `body_extension_fraction` 기본값과 설정값을 `0.15`로 낮췄다. 본체 폭의
  중앙값보다 `8%` 이상 큰 구간이 이 기준 이상 반복될 때만 해당 축을
  본체 경계로 보정한다.
- 현재 저장 프레임 기준 조립 기판 박스 중심은 약 `(1230.4, 494.4)px`,
  장축 각도는 `+11.9°`이며, 손잡이로 추정되는 상단 돌출을 제외한 박스로
  계산된다. 빈 기판 결과도 기존 본체 중심 `(582.6, 484.3)px`를 유지한다.
- 테스트 `23 passed`, ROS 패키지 재빌드 성공. 실제 화면에 반영하려면
  S22/ROI 노드를 재시작해야 한다.

## 2026-08-21 - 조립 기판 회전 박스의 원근 보정

- 손잡이 제거 후에도 회전된 조립 기판에서 enclosing `minAreaRect`가 남아
  본체 모서리와 조금 어긋날 수 있는 문제가 확인됐다.
- 본체 외곽선에서 최소 epsilon으로 convex 4점 polygon을 추출하고, 이 4점을
  오버레이 박스와 중심 계산에 직접 사용하도록 수정했다. 따라서 S22가 비스듬히
  설치된 상태의 사다리꼴 원근도 그대로 표시한다.
- 저장된 실제 프레임 기준 결과: 빈 기판은 중심 약 `(581.8, 484.2)px`,
  조립 기판은 중심 약 `(1229.8, 494.8)px`, 장축 각도 `+11.5°`로 계산되며
  조립 기판의 4점은 `[(1118,383), (1056,547), (1341,608), (1404,441)]`이다.
- 방향 표시 각도도 전체 외곽선이 아니라 본체 4점에서 계산하도록 변경했다.
  테스트 `23 passed`를 다시 확인했다.

## 2026-08-27 - S22 정지선 화면 누락과 프레임 저하 점검

- 당시 구 실행기로 카메라를 실행한 뒤 `/camera2/image_raw/compressed`를 보면 정지선이
  보이지 않는다는 문제를 점검했다. 카메라와 `/conveyor_roi` 노드는 모두 정상
  실행 중이었으며, 정지선은 설계대로 별도 토픽
  `/vision/conveyor/stop_image/compressed`에만 그려지는 것을 확인했다.
- 실행기에 원본 카메라 토픽은 정지선 없는 영상이고, 정지선 확인 토픽은
  `/vision/conveyor/stop_image/compressed`라는 안내를 추가했다.
- ROI 검출은 full-HD 원본에서 유지하되 주석 출력만 1280 px/JPEG 78로 경량화했다.
- Python/YAML 검사, `vision_server` 테스트 23개 통과 및 ROS 패키지 재빌드 완료.
- Wi-Fi 실행기에도 동일한 경량 ROI 출력을 적용하고, 실행 로그에서 정지선 확인
  토픽과 원본 토픽의 차이를 바로 안내하도록 했다. 실제 시험에서
  `/conveyor_roi`가 두 정지선 설정과 함께 정상 시작되는 것을 확인했다.

## 2026-08-31 - S22 컨베이어 실행기 scrcpy 단일화

- 사용하지 않는 스마트폰 앱 기반 USB·Wi-Fi 카메라 실행기를 제거하고 컨베이어
  감시 실행을 `~/KSMC/run_s22_conveyor_hq.sh`로 단일화했다.
- 조립·검사 정지선 ROI 노드, 영상 토픽과 자동 검사 trigger 계약은 변경하지
  않았다. 정리 중 실제 컨베이어 구동 명령은 전송하지 않았다.
- 새 HQ 실행기를 18초간 영상 전용으로 실행해 `/conveyor_roi`가 조립선
  `0.22032`, 검사선 `0.48071`, trigger lead `10 px`, `/cmd_vel` publisher 없음으로
  시작되는 것을 확인했고 종료 후 잔여 프로세스도 없었다.

## 2026-08-27 - 컨베이어 검출 파이프라인 추가 최적화

- S22 원본 토픽은 `1920×1080/JPEG 85`로 보존하고, 정지선 검출과 오버레이만
  내부에서 최대 폭 `1280 px`로 처리하도록 분리했다. 정지선·검색 영역은 모두
  정규화 좌표이므로 영상 축소 후에도 화면상의 상대 위치와 정지 판정은 유지된다.
- 정지선 오버레이는 `1280 px/JPEG 85`로 발행한다. 기존 JPEG 78보다 표시 화질을
  높이면서 Full-HD 재인코딩 부하와 DDS/rqt 전송량은 줄였다.
- 카메라와 ROI 입출력 모두 최신 1프레임 QoS를 사용해 오래된 프레임 누적이
  정지 반응을 늦추지 않게 했다. Vision 회귀 테스트 `23 passed`, Python/YAML 및
  USB/Wi-Fi 실행기 구문 검사, `vision_server` 재빌드를 완료했다.

## 2026-08-31 — 비전검사 정지 후 자동 촬영·검사

- `/vision/conveyor/inspection/stop_trigger`가 참이 되면 모터 정지와 별개로 0.35초
  안정화 후 S22 망원 촬영, 기판 ROI 추출, 전수검사를 실행하도록 연결했다.
- trigger가 계속 참이어도 한 기판당 한 번만 실행한다. 기판이 정지선에서 20 px
  이상 벗어난 상태가 0.5초 유지된 뒤에만 재무장한다.
- 중복 trigger 프로세스를 막는 파일 lock, 종료 시 자식 촬영/검사 프로세스 정리,
  이전 latest 결과 재사용 차단, 상태·결과·report 경로 ROS 토픽을 추가했다.
- 실제 컨베이어 구동에서 검사선 정지와 자동 검사 시작을 확인했다. 이 노드는
  `/cmd_vel`을 발행하지 않으며 컨베이어 이동은 기존 별도 제어기가 담당한다.

## 2026-08-31 — 검사 정지 후 촬영 전용 데이터 수집

- `/vision/conveyor/inspection/stop_trigger`를 재사용해 검사 위치 정지 0.35초 후
  S22 망원 촬영만 수행하는 수집 모드를 추가했다. 기존 OpenCV 불량 판정은 이
  경로에서 실행하지 않는다.
- trigger가 계속 참인 같은 기판은 한 번만 촬영하며, 다음 기판이 upstream에서
  확인된 뒤에만 재무장한다. 촬영 trigger 실행기는 모터 명령을 발행하지 않고
  실제 이동은 `run_conveyor_to_inspection.sh`에서만 수행한다.
- 현재 SMD가 없는 기판은 `known_defect/missing_smd`로 명시하여 정상 데이터와
  분리한다. 모의 촬영 및 gate 테스트 5개가 통과했으며, 이번 변경 중 실제 모터
  명령은 전송하지 않았다.

## 2026-08-31 — 카메라 프레임 저하 시 정지선 통과 방지

- S22 제어 입력을 약 22 FPS에서 29 FPS 이상으로 개선하고, 기판 검출 직후 UI
  렌더링보다 먼저 stop trigger를 발행하도록 변경했다. 화면용 오버레이 FPS와
  물리 정지 판단 FPS는 서로 독립적이다.
- source timestamp 기준 0.20초 이상 지연된 프레임은 사용하지 않는다. 비전
  ready/trigger가 0.25초 동안 갱신되지 않아도 컨베이어 제어기가 즉시 0속도를
  발행한다.
- `/cmd_vel` publisher를 reliable depth 10에서 KEEP_LAST(1)로 바꿔 네트워크 정체
  시 과거 속도 명령이 zero 명령보다 먼저 재생될 가능성을 제거했다. 제어 확인
  주기는 20 Hz에서 50 Hz로 높였다.
- 테스트 30개와 ROS 빌드를 통과했고 S22+정지선만 무동작 실측했다. 실제 0.10 m/s
  재주행은 아직 수행하지 않았다.

## 2026-09-01 — 새 S22 위치의 2개 정지선 확정 및 정지 선행 보상

- S22 overview를 1.5배로 다시 고정한 화면에서 기판 2개 검출을 확인했다.
  960px 제어 폭 기준 수동 배치 trailing edge 초기값은 조립 `175.69px`, 검사
  `574.67px`였고 정지선을 각각 `0.18301061`, `0.59861813`으로 저장했다.
  정지선 간 정규화 간격은 `0.41560752`이며 spacing interlock은 true였다.
- 사용자가 실제 0.10m/s 컨베이어 구동에서 기존 `stop_trigger_lead_px=10`으로
  선을 지난 뒤 정지하는 잔차를 확인했다. 화면의 목표선은 이동하지 않고 제어
  trigger만 20px 먼저 발생하도록 변경했다.
- 프레임 지연 시 계속 이동하는 시간을 줄이기 위해 stale cutoff를 0.15초,
  controller heartbeat timeout을 0.15초로 단축했다. trigger callback의 즉시
  zero publish, 20ms 반복 zero, reliable KEEP_LAST(1) 명령 QoS는 유지했다.
- 설정 적용 후 ROI 노드 로그에서 assembly `0.18301`, inspection `0.59862`,
  lead `20.0px`, stale cutoff `0.150s`, `/cmd_vel` publisher 없음이 확인됐다.
  테스트 `35 passed`와 bash 구문 검사를 통과했다.
- 이번 수정·검증에서는 로봇과 컨베이어 실제 명령을 전송하지 않았다. 사용자가
  보고한 기존 실동작 overrun을 근거로 한 1차 보정이므로 같은 0.10m/s에서 다시
  주행해 정지 잔차를 측정하고 필요하면 lead만 소폭 조정해야 한다.

## 2026-09-01 — 비전 검사 정지 위치 최종 변경

- 사용자가 선택한 새 물리 위치에서 3.5배 검사 원본에 기판 전체가 들어오는 것을
  확인한 뒤, 1.5배 overview의 trailing edge `503.7585px/960px`를 검사선으로
  사용했다. inspection line을 `0.59861813`에서 `0.52474848`로 변경했다.
- assembly line `0.18301061`과 stop trigger lead `20px`는 유지했다. 새 정지선
  간격 `0.34173787`은 minimum separation `0.20`을 만족한다.
- 노드 재시작 로그에서 assembly `0.18301`, inspection `0.52475`, separation
  `0.34174`, lead `20.0px`, `/cmd_vel` publisher 없음이 확인됐다. 테스트는
  `35 passed`였고 이번 적용에서 실제 모터 명령은 보내지 않았다.

## 2026-09-01 — 검사 정지선 최신 수동 위치 반영

- 현재 기판 trailing edge를 `485.0px/960px`로 다시 측정해 inspection line을
  `0.52474848`에서 `0.50520833`으로 옮겼다. assembly line `0.18301061`과
  trigger lead `20px`는 변경하지 않았다.
- 새 separation `0.32219772`는 안전 기준을 통과했고 테스트는 `35 passed`였다.
  사용자 요청에 따라 실행 중 ROI 노드는 재시작하지 않았으며 실제 `/cmd_vel`
  명령도 보내지 않았다.

## 2026-09-03 — Main Server/Unity용 원격 컨베이어 서비스

- 상시 실행형 `conveyor_remote_server`를 추가하고
  `/conveyor/move_to_assembly`, `/conveyor/move_to_inspection`,
  `/conveyor/stop`, `/conveyor/reset` Trigger 서비스를 구현했다.
- `/conveyor/state`에 10 Hz JSON 상태 heartbeat, `/conveyor/moving`에 명령 기준
  이동 여부를 발행한다. 상태는 IDLE, 두 station 이동/정지, MANUAL_STOP,
  FAULT를 구분한다.
- 실제 속도 권한은 이 서버 하나만 갖는다. 다른 `/cmd_vel` publisher가 있으면
  출발을 거부하고 이동 중 발견 시 FAULT 정지한다. 기존 검증값인
  `TwistStamped.linear.x=-0.10 m/s`, S22 heartbeat 0.15초, 최대 이동 30초를
  적용했다.
- `/cell/fr5_clear_for_conveyor=True`가 0.25초 안에 갱신돼야 출발한다. 이동 중
  false 또는 timeout이면 즉시 0속도와 FAULT를 발행한다. 실제 FR5 clear
  publisher는 Main/Robot executor에서 아직 연결해야 한다.
- `assembly-r1`의 `move_conveyor_to_assembly`와
  `move_conveyor_to_inspection` operation을 각각 서비스에 매핑하고, 서비스 수락이
  아닌 ASSEMBLY_STOP/INSPECTION_STOP 상태를 operation 완료 조건으로 정의했다.
- 원격 서버 실행은 `--execute --confirm-motion`을 모두 요구한다. monitor-only
  검증에서 이동 요청 거절, stop 성공, MANUAL_STOP JSON을 확인했다. 별도 ARMED
  검증에서는 네 안전 heartbeat 아래 assembly 이동 수락, 격리 토픽의
  `linear.x=-0.10`, 비전 trigger 이후 `ASSEMBLY_STOP/moving=false` 전이를
  확인했다. 검증용 명령은 `/test/conveyor_cmd_vel`로 격리해 실제 로봇·컨베이어에는
  어떤 이동 명령도 보내지 않았다.
- Vision 패키지 전체 47개 테스트와 ROS 빌드가 통과했다. 상세 팀 연동 계약은
  `docs/CONVEYOR_API_HANDOFF.md`에 기록했다.
## 2026-09-10 Bundle startup false-positive repair

- Diagnosed startup refusal: `/conveyor/move_to_assembly`, `/conveyor/move_to_inspection`
  and `/conveyor/stop` were visible in the ROS graph, but `ros2 service info` reported
  `Services count: 0` and only `/conveyor_roi` was present as a client. rclpy's graph
  service-name query combines client/server names, so the bundle incorrectly treated
  teammate clients as an existing server and exited before launching.
- Removed the graph-name duplicate refusal. Local server process detection, HTTP port
  reservation and bundle lock remain duplicate guards. Startup readiness now requires
  the local HTTP listener and a local owned server process; graph names remain only
  diagnostic/readiness hints. No service call, motor command or robot command was sent.
- Updated regression test to allow remote client names. Full vision/integration test
  suite after the repair: 508 offline tests passed (three socket tests excluded).
  Actual server restart and teammate request remain pending operator execution.
## 2026-09-10 Asynchronous stop overlay

- Same reported motion_id reproduced in local log: accepted at1789004707.683,
  heartbeat fault at1789004708.457, ROI stale-frame rejection age183ms at
  1789004708.468. Camera five-second averages near29FPS do not exclude latency
  spikes; other ROI frames exceeded150ms. Teammate MCAP is not local.
- Moved dashboard drawing/JPEG publication to one bounded render worker, using
  frozen station snapshots. Busy renderer skips intermediate displays; controls
  continue on incoming frames. Worker finishes before publisher destruction.
  Image age and heartbeat limits unchanged. This removes one blocking source;
  no claim yet that all capture/detection/DDS latency is resolved.
- Runtime system Python ROI tests45passed. PatchCore venv runs had six existing
  NumPy2 two-dimensional-cross incompatibility failures; not used for camera runtime.
  No live restart, motor request or network change. Deployment requires restarting
  the stop-line node while conveyor stopped; live latency must then be measured.

## 2026-09-11 — Request-time recovery after a manually returned board

- Reproduced the reported retry delay in the controller: passive completion
  cleanup required 20 distinct empty frames spanning 2 seconds. That window
  remains in place for unattended automatic IDLE recovery.
- Added a separate explicit-request path. When the controller is latched at
  `ASSEMBLY_STOP` or `INSPECTION_STOP`, a new move request can clear the old
  completion after both station observations have fresh empty evidence for
  5 frames spanning 0.4 seconds. The old motion ID, arrival record and stop
  triggers are cleared before the request is validated, so the same request
  can start a new motion without `/conveyor/reset`.
- Empty evidence still requires a fresh stopped motor state, matching server
  and motion IDs, a fresh source image, and both station regions clear. A board
  still at either station, stale evidence, or another `/cmd_vel` publisher
  continues to reject the request. `MANUAL_STOP` can be recovered only by this
  explicit empty-evidence request; `FAULT` still requires `/conveyor/reset`.
- The S22 empty-belt mask now excludes only a valid detected polygon whose
  trailing edge is at least 30 px upstream of the assembly line. This
  covers a board physically returned to the start position without treating a
  board crossing the assembly line as empty; unknown dark obstructions still
  veto the evidence.
- Offline regression validation passed 158 conveyor arrival, remote-server,
  and ROI tests, including the new short-window restart and upstream-board
  cases. No live move, stop, reset, robot command, or teammate Endpoint process
  was started or restarted during this change. A physical retry still requires
  the board to be visibly clear of both station footprints and a supervised
  operator test.

# Codex Handoff — KSMC FR5 Vision Assembly Cell

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
- TurtleBot used for conveyor prototype: `192.168.11.101`, model `burger`.
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

`run_s22_conveyor.sh` publishes the S22 image and dual stop-line detection.
The first line is the assembly station and the downstream line is the vision
inspection station. `run_conveyor_to_assembly.sh` and
`run_conveyor_to_inspection.sh` command one explicitly selected movement at
0.10 m/s. Vision/trigger heartbeat loss, invalid two-board station spacing and
Ctrl+C publish zero speed. The original single-line hardware stop was tested;
the new two-line extension has passed software tests but still needs final
hardware line registration and a physical stop test. This is a prototype
auxiliary control, not a certified safety function.

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
  `docs/logs/conveyor.md`
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

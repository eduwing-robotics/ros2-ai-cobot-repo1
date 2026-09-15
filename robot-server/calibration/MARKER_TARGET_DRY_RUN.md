# ArUco marker target dry run

This test selects one marker ID on the configured ChArUco board, estimates the
full board pose from all available ChArUco corners, and transforms the selected
marker center from the camera frame to the FR5 base frame using the saved
Eye-in-Hand result.

It is a dry run by default and never sends a robot motion command unless both
`--move` and `--confirm-move` are explicitly supplied.

## Before starting

- Fix the marker so it cannot move.
- Use the same dictionary as the marker: the current KSMC configuration is
  `DICT_5X5_50`.
- Set `--marker-length-mm` to the physical side length of the selected marker.
  The default is the current ChArUco marker size, 16.8 mm.
- Keep the robot stationary while the target is being calculated.
- `toolcoord1` must already be active. Its calibrated TCP is used by FR5
  `MoveCart`; the flange-to-TCP distance is not added in this program.
- The node waits until the flange pose has remained stable for one second,
  then collects frames. Once acquired, the target is locked and camera images
  received during motion cannot change it.

## Run

Source the ROS and FR5 workspaces automatically with:

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_marker_target_dry_run.sh \
  --marker-id 0 \
  --approach-offset-mm 100 \
  --frames 20 \
  --dry-run
```

For the first real motion test, use the same command with both motion flags.
This uses staged `MoveCart` commands: vertical raise when needed, Tool +Z
alignment to the board normal while preserving finger yaw, horizontal
positioning at a safe Z, then a vertical non-contact approach. It uses Tool
1/Base user 0 and does not move to the marker surface or actuate the gripper:

```bash
/home/juchan-yoon/FR5_robot_control/calibration/run_marker_target_dry_run.sh \
  --marker-id 0 \
  --marker-length-mm 16.8 \
  --approach-offset-mm 100 \
  --frames 20 \
  --speed-percent 40 \
  --descent-speed-percent 15 \
  --safe-clearance-mm 50 \
  --execute --confirm-move
```

Before running the motion command, clear the robot workspace, keep the
emergency stop reachable, confirm `tool_num` is 1, and put the FR5 in AUTO
mode (`robot_mode: 0`) with the robot enabled. The script rejects motion in
manual mode (`robot_mode: 1`). The default maximum travel is 600 mm and can be
reduced with `--max-distance-mm`.

If a previous `MoveCart` was sent while the robot was still in manual mode,
stop and restart the FR5 command-server process before changing to AUTO. This
clears the potentially pending service command so it cannot start later.

Replace `0` with the marker ID that should be selected. If the marker is a
separate print, use its actual physical side length instead of 16.8 mm.

The node prints:

- marker center in the FR5 base frame;
- camera-side approach point at the requested offset;
- marker +Z normal in the base frame;
- center repeatability over the stable frames.
- ArUco/ChArUco `rvec` and `tvec`;
- `T_base_flange`, `T_flange_camera`, `T_camera_board`,
  `T_base_marker`, and `T_base_target`.

The annotated image is published on:

```text
/calibration/marker_target/image_annotated/compressed
```

Select that topic in `rqt_image_view` to confirm that the requested marker ID
is the one being used. The latest dry-run summary is saved to:

```text
/home/juchan-yoon/FR5_robot_control/calibration/data/marker_target_last.json
```

The next stage must use the printed approach point for a non-contact move first;
the motion-enabled invocation still does not descend or operate the gripper.

The motion path is rejected when the ChArUco pose jitter exceeds 2 mm, the
board is tilted more than 20 degrees, or Tool +Z is not approximately directed
toward the board. If motion looks unsafe, use the FR5 stop/pause or emergency
stop; `Ctrl+C` is not guaranteed to cancel a command already accepted by the
controller.

The script sends explicit `SetSpeed` and `MoveCart` speed values, so changing
only the WebApp speed slider does not increase this test's commanded speed.
`--speed-percent` controls safe-height horizontal positioning (default/max
40%). Rotation, raising, and the final vertical approach remain limited by
`--descent-speed-percent` (default 15%, max 25%).

The empirical camera-to-TCP correction in `config/charuco_board.yaml` is zero.
The side-mounted camera offset is already represented by
`T_flange_camera`; the calibrated TCP is already represented by FR5
`toolcoord1`. Do not add either offset again.

## Transform convention

Every transform is named `T_parent_child` and maps coordinates from `child`
to `parent`:

```text
p_parent = T_parent_child @ p_child
T_base_board = T_base_flange @ T_flange_camera @ T_camera_board
```

`cv2.calibrateHandEye()` produces camera-to-gripper. In this project the
gripper calibration frame is the FR5 flange, therefore the saved
`camera_to_flange` value is loaded as `T_flange_camera`.

The default approach direction is Robot Base +Z. This preserves target Base
X/Y and adds only the requested safety height. The previous camera-facing
board-normal behavior remains available with `--approach-frame board_normal`.

## Independent validation

Capture at least five poses that were not used to solve the calibration:

```bash
source /opt/ros/jazzy/setup.bash
source /home/juchan-yoon/FR5_robot_control/robot_ws/install/setup.bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/capture_charuco_handeye_sample.py \
  --data-file /home/juchan-yoon/FR5_robot_control/calibration/data/validation_samples.json
```

Move to a distinct translation and rotation before each invocation. Then run:

```bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/validate_handeye_samples.py
```

This offline command never moves the robot. It prints per-pose X/Y/Z and
Euclidean errors plus mean, median, and maximum errors.

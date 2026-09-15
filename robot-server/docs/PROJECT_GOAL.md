# KSMC Project Goal

## Final objective

Build an **FR5-based precision assembly and inspection smart manufacturing
cell for semiconductor-package-style electronic modules**.

The final system is not an ArUco tracker or a simple pick-and-place demo. It
must integrate:

```text
Conveyor arrival
  -> fixed/eye-in-hand vision localization
  -> FR5 precision pick and assembly
  -> post-assembly vision inspection
  -> PASS/FAIL decision
  -> UI and process log
```

The workpieces are 3D-printed or otherwise simulated package substrates,
interposers, GPU/AI dies, HBM modules, heat spreaders, and small components.

## Hardware roles

- **FAIRINO FR5:** pick, safe approach, visual correction, precision placement,
  re-approach, and inspection positioning.
- **DH Robotics PGEA-100-40:** active gripper. `toolcoord1` was calibrated by
  the FR5 four-point TCP procedure; TCP Z is approximately 165 mm. Do not
  modify or duplicate this offset in application transforms.
- **Intel RealSense D435:** side-mounted Eye-in-Hand camera for fiducial,
  board, and part localization; robot-coordinate conversion; near-field
  correction; placement inspection; and optional aligned depth measurement.
- **Fixed smartphone camera:** future conveyor/assembly-station detection,
  board arrival and skew estimation, and wider post-assembly inspection.
- **GoPro/wide camera:** optional cell overview and supplemental person/zone
  monitoring. It is not a replacement for rated robot safety functions.

Camera inputs must be abstract enough to add fixed and wide cameras later;
core geometry must not be hard-coded to one image topic.

## Process target

1. Start conveyor.
2. Detect substrate/interposer arrival.
3. Stop conveyor.
4. Detect board fiducials and estimate position/orientation error.
5. Transform the board pose into FR5 Base.
6. Detect and pick a component from its tray.
7. Apply vision-based near-field correction.
8. Place it at the board-defined target.
9. Repeat for GPU/AI die, HBM, heat spreader, and selected small components.
10. Inspect presence, omission, identity, translation, rotation, and assembly
    state.
11. Produce PASS/FAIL and record the result in UI/terminal/logs.
12. Optionally route good and rejected assemblies later.

## Development phases

1. Camera-to-robot coordinate accuracy.
2. ArUco/fiducial board localization and correction.
3. Pick-position perception.
4. FR5 pick motion.
5. Precision placement on the board.
6. Multi-component sequential assembly.
7. Post-assembly vision inspection.
8. PASS/FAIL decision.
9. Conveyor integration.
10. Full automatic process, UI, and logging integration.

The current phase ends only when a point observed by the D435 maps reliably to
the physical FR5 TCP. The immediate safety test targets 100 mm above a detected
marker; it does not descend to or grasp the marker.

## Transform convention

Use explicit frames at minimum:

```text
base, flange, tool/tcp, camera, marker, board, part, target
```

Name transforms `T_parent_child`, meaning the matrix maps a point from child
coordinates into parent coordinates:

```text
p_parent = T_parent_child @ p_child

T_base_marker =
    T_base_flange @ T_flange_camera @ T_camera_marker
```

Future assembly geometry may include:

```text
T_marker_board
T_board_part_target
T_part_grasp
```

Avoid ambiguous names such as `offset_x`, `temp_x`, or `robot_xyz` when a
frame-qualified transform or vector can be used.

## Architecture principles

- Keep and improve reusable calibration, perception, transform, motion,
  inspection, conveyor, state-machine, UI, and logging modules.
- Do not solve camera-to-robot geometry by directly adding camera XYZ to robot
  XYZ.
- Do not add empirical per-marker XY constants as a substitute for Hand-Eye,
  TCP, board, or grasp transforms.
- Do not assume camera optical axes equal Base, Flange, or Tool axes.
- Do not assume a single marker, fixed robot pose, or fixed camera pose.
- Do not reuse the calibrated 165 mm TCP distance as an application offset.
- Preserve calibrated Hand-Eye results for all later Camera-to-Base
  transformations, with explicit versioning when the mount changes.
- Synchronize image observations and robot poses; lock a target before motion.
- Keep RGB-only PnP valid independently of depth. If depth is used, align depth
  to color before associating RGB pixels with depth pixels.

## Safety invariants

- Dry-run is the default; execution requires explicit user confirmation.
- Current tests stop at 100 mm above the marker and never auto-descend.
- Use low speed, staged motion, travel limits, and workspace checks.
- Reject NaN, Inf, implausible transforms, large jumps, excessive visual
  jitter, missing calibration, incorrect Tool ID, and unsafe robot state.
- A target is computed from settled, time-consistent data and then locked;
  images received during motion cannot update it.
- `MoveCart` targets are TCP poses using active `toolcoord1`; Hand-Eye uses the
  Base-to-Flange pose. Do not mix the two.
- Camera-based person detection is supplemental only. Physical emergency stop
  and validated robot safety functions remain authoritative.
- `Ctrl+C` may stop the client without cancelling a command already accepted
  by the controller; use FR5 Stop/Pause or emergency stop for unsafe motion.

## Decision rule for every change

Before accepting an implementation, ask:

> Can this calibration, transform, perception result, command, and log be
> reused as part of the eventual conveyor + vision + FR5 + assembly +
> inspection manufacturing cell?

Prefer progressive modular improvement over isolated demonstration code.

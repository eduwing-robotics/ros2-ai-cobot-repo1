# Common safe tray-part pick approach

Use `run_safe_part_pick.sh` for every camera-guided tray pick. The workflow is intentionally split so an operator can inspect the center before the robot reaches grasp height.

## Supported recipes

Run:

```bash
vision_assembly/run_safe_part_pick.sh status
```

HBM, Power Module, VRM, and Inductor are enabled when their center correction, grasp-height offset, and gripper recipe are complete. GPU and SMD Capacitor remain blocked until their missing calibration values are taught.

## Phase 1: prepare and stop 20 mm above the part

Dry-run first:

```bash
vision_assembly/run_safe_part_pick.sh prepare --part inductor --instance 3 --dry-run
```

Execute only after reviewing the plan:

```bash
vision_assembly/run_safe_part_pick.sh prepare --part inductor --instance 3 \
  --execute --confirm-prepare
```

This phase performs a fresh stable detection, loads the part recipe, rotates at safe height, moves horizontally at safe height, descends vertically to 20 mm above the detected surface, verifies the actual TCP, and writes a short-lived hover session.

## Phase 2: verified Base-Z-only descent

After visually confirming the center, dry-run:

```bash
vision_assembly/run_safe_part_pick.sh descend --part inductor --instance 3 --dry-run
```

Then execute:

```bash
vision_assembly/run_safe_part_pick.sh descend --part inductor --instance 3 \
  --execute --confirm-center --confirm-descent
```

Before moving, this phase requires the robot to still be at the verified hover pose and performs a fresh detection. It rejects more than 2 mm of XY or Z drift, more than 2 degrees of angle drift, stale/mismatched sessions, unsafe descent distance, robot errors, or a changed tool/frame. The final command preserves current XY and orientation and changes Base Z only. It stops at grasp height with the gripper still open.

Legacy continuous-descent full-pick entry points are disabled. Gripper closing and lifting must only be added after the common approach has been physically validated for every enabled part family.

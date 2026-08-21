# Hand-Eye refinement pose plan

All poses start from the saved reference observation pose where the complete
ChArUco board is detected. Return to that saved pose before constructing every
new pose; do not accumulate jogs from the previous sample.

Use FR5 WebApp Cartesian motion only:

- translations: **Base** X/Y/Z;
- camera tilts and image rotation: **Tool** RX/RY/RZ;
- low manual speed, preferably 5-10%;
- perform rotations only at the high observation pose, never near the board.

| Pose | Start | WebApp frame and relative jog |
|---|---|---|
| 1 | Saved reference | No change |
| 2 | Saved reference | Tool RY +10 deg |
| 3 | Saved reference | Tool RY -10 deg |
| 4 | Saved reference | Tool RY +15 deg |
| 5 | Saved reference | Tool RY -15 deg |
| 6 | Saved reference | Tool RX +10 deg |
| 7 | Saved reference | Tool RX -10 deg |
| 8 | Saved reference | Tool RX +15 deg |
| 9 | Saved reference | Tool RX -15 deg |
| 10 | Saved reference | Tool RZ +15 deg |
| 11 | Saved reference | Tool RZ -15 deg |
| 12 | Saved reference | Base Z +60 mm (farther/higher) |
| 13 | Saved reference | Base Z -50 mm (closer/lower; only with clearance) |
| 14 | Saved reference | Base X +40 mm, Base Y +30 mm, then Tool RY +10 deg and Tool RX -8 deg |
| 15 | Saved reference | Base X -40 mm, Base Y -30 mm, then Tool RY -10 deg and Tool RX +8 deg |

For each pose, verify the board remains in frame, stop the robot, wait at least
one second, then run:

```bash
python3 /home/juchan-yoon/FR5_robot_control/calibration/scripts/capture_charuco_handeye_sample.py \
  --data-file /home/juchan-yoon/FR5_robot_control/calibration/data/handeye_refinement_samples.json
```

Prefer 17/17 markers and 24/24 ChArUco corners; never capture fewer than 12
corners. If a requested tilt loses too many corners or creates a collision
risk, reduce that angle while preserving the sign and record the actual angle.

Base Z+ is expected to move away from the horizontal board and Base Z- toward
it in the current cell. Verify the first 5 mm jog visually before completing
poses 12 or 13. Tool rotation keeps the configured TCP XYZ fixed, but the
side-mounted D435 and its bracket sweep through space; check their clearance.

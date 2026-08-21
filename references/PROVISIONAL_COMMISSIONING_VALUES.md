# Provisional Home and Gripper Values

## Status

- Recorded: 2026-08-17
- Source: operator-provided values from the current FR5/PGEA setup
- Classification: commissioning input only; not production-approved
- Activation: not loaded by `fr5_bringup` or any production recipe

The numeric meaning and units of the `MoveGripper` arguments must be confirmed against the installed FAIRINO/PGEA interface before conversion to typed recipe parameters.

## Candidate part-pick home pose

This pose was identified as the likely home position used before picking parts.

| Joint | Angle (deg) |
|---|---:|
| J1 | 0 |
| J2 | -90 |
| J3 | 90 |
| J4 | -90 |
| J5 | -90 |
| J6 | 0 |

Joint vector in `J1..J6` order: `[0, -90, 90, -90, -90, 0] deg`.

## Read-only observation — 2026-08-17

A command-free SDK session to `192.168.58.2` returned a valid six-joint sample. No motion, servo, mode, I/O, or gripper API was exposed or called, and the session then shut down cleanly.

| Joint | Observed (rad) | Observed (deg, approximate) | Candidate home (deg) |
|---|---:|---:|---:|
| J1 | 0.05354884 | 3.068 | 0 |
| J2 | -1.53911430 | -88.185 | -90 |
| J3 | 1.58359974 | 90.733 | 90 |
| J4 | -1.56797138 | -89.838 | -90 |
| J5 | -1.58579059 | -90.859 | -90 |
| J6 | 0.00021263 | 0.012 | 0 |

This confirms that the robot was near, but not exactly at, the candidate home pose. It does not approve or command that pose.

## Provisional part gripper values

The first command in each pair is interpreted provisionally as **grip** and the second as **release**. Verify this on the installed device before execution.

| Part | Orientation | Grip position | Release position | Speed | Force/torque parameter | Timeout (ms) |
|---|---|---:|---:|---:|---:|---:|
| GPU | unspecified | 65 | 70 | 50 | 30 | 3000 |
| HBM | unspecified | 18 | 25 | 50 | 30 | 3000 |
| Power Module | unspecified | 26 | 30 | 50 | 30 | 3000 |
| VRM | horizontal | 24 | 26 | 50 | 30 | 3000 |
| VRM | vertical | 32 | 34 | 50 | 30 | 3000 |
| Inductor | unspecified | 16 | 20 | 50 | 30 | 3000 |
| SMD Capacitor | unspecified | 5 | 8 | 50 | 1 | 3000 |

## Original commands

```text
GPU grip:                 MoveGripper(1,65,50,30,3000,0,0,0,0,0)
GPU release:              MoveGripper(1,70,50,30,3000,0,0,0,0,0)
HBM grip:                 MoveGripper(1,18,50,30,3000,0,0,0,0,0)
HBM release:              MoveGripper(1,25,50,30,3000,0,0,0,0,0)
Power Module grip:        MoveGripper(1,26,50,30,3000,0,0,0,0,0)
Power Module release:     MoveGripper(1,30,50,30,3000,0,0,0,0,0)
VRM horizontal grip:      MoveGripper(1,24,50,30,3000,0,0,0,0,0)
VRM horizontal release:   MoveGripper(1,26,50,30,3000,0,0,0,0,0)
VRM vertical grip:        MoveGripper(1,32,50,30,3000,0,0,0,0,0)
VRM vertical release:     MoveGripper(1,34,50,30,3000,0,0,0,0,0)
Inductor grip:            MoveGripper(1,16,50,30,3000,0,0,0,0,0)
Inductor release:         MoveGripper(1,20,50,30,3000,0,0,0,0,0)
SMD Capacitor grip:       MoveGripper(1,5,50,1,3000,0,0,0,0,0)
SMD Capacitor release:    MoveGripper(1,8,50,1,3000,0,0,0,0,0)
```

## Required confirmation before activation

- Confirm the exact `MoveGripper` argument contract and units for the installed controller, firmware, and gripper.
- Confirm that lower position values mean a tighter/closed gripper.
- Confirm that the fourth argument value `1` for SMD Capacitor is intentional; all other supplied commands use `30`.
- Measure commanded versus actual opening and verify retention, damage, slip, and release.
- Assign tool, finger, part, and recipe revisions before promoting values to executable recipes.

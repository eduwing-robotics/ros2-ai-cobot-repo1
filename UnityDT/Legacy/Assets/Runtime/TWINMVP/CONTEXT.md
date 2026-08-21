# TWIN MVP context

## Boundary

- All MVP source changes live under `Assets/Runtime/TWINMVP`.
- Existing FR5, camera, scene and Farino_AIO sources are referenced but not edited.
- Pre-work checkpoint: `58946a6 chore: checkpoint gripper ROS adapter state`.

## Purpose

Validate this path quickly without a RealSense device:

```text
Unity Depth Cam -> RGB + synthetic aligned depth + CameraInfo
-> copied AIO HSV/depth detector -> PointStamped
-> Unity Vision Adapter -> existing PickPlaceOrchestrator -> MoveIt bridge
```

Synthetic depth is the assigned `scanPoint` camera-space Z in millimetres,
filled across the frame. It validates transport, HSV detection, pinhole
projection and orchestration. It does not validate occlusion or surface depth.

## Scene setup

1. Add `TwinMvpScenarioOrchestrator` to a new scene GameObject.
2. Use `TWIN MVP/Install Demo Components` from its component context menu.
3. Populate `Parts` in assembly order.
   - `label`: one of `chip`, `led`, `tantal`, `sot`, `pinheader`, `cond`.
   - `part`: actual PLATE part.
   - `scanPoint`: manually placed scan/grasp reference.
   - `pickOrientation`: optional TCP orientation; otherwise scanPoint rotation.
   - `placeTarget`: PCB assembly target.
   - `visionMarker`: optional saturated-color marker visible to Depth Cam.
   - `localGraspOffset`: calibration knob in scanPoint coordinates.
4. Match marker colors to `AIO/part_colors.json`. Only the current marker is
   enabled during a scan.
5. Run `TWIN MVP/Run Local Smoke Test` before entering Play Mode.
6. In Play Mode run `TWIN MVP/Scan First Part` or `Scan Next Part`.

The existing FR5 `PickPlaceOrchestrator` remains the owner of target poses and
planning. Set `Plan After Detection` only after the existing Unity/MoveIt plan
bridge is running.

## AIO detector

From the Unity project root:

```bash
python3 Assets/Runtime/TWINMVP/AIO/hsv_depth_multi_detector.py --self-test
python3 Assets/Runtime/TWINMVP/AIO/hsv_depth_multi_detector.py
```

Published topics:

```text
/fr5_vision/chip/point
/fr5_vision/led/point
/fr5_vision/tantal/point
/fr5_vision/sot/point
/fr5_vision/pinheader/point
/fr5_vision/cond/point
```

Points use metres in `sim_camera_optical_frame` (`+x` right, `+y` down,
`+z` forward). The Unity adapter converts them with the assigned Depth Cam
transform.

## Context-menu checks

- Depth Cam Publisher: `Publish One Scan Frame`, `Validate Depth Camera`.
- Vision Adapter: `Simulate Detection`, `Validate Vision Adapter`.
- Scenario Orchestrator: install, scan, prepare, plan, smoke-test and validate.

## Deferred after MVP

- Replace uniform synthetic depth with URP linear-depth rendering.
- Detect actual part materials instead of dedicated colored markers.
- Add Planning Scene attach/detach and placed-part collision objects.
- Replace manually assigned scan points only if real perception requires it.

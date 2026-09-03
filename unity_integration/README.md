# D435 tray to Unity digital-twin synchronization

## 관제 연동 기준

이 문서의 /vision/tray/unity_state JSON 구독기는 실시간 미리보기용 레거시 경로다. 실제 조립 사이클의 권위 있는 계약은 /vision/tray/detect_parts 및 /vision/pcb/calibrate_pose 두 Action이며, 상세 계약은 docs/unity_vision_actions_ko.md를 따른다.

The tray detector publishes a complete, camera-derived snapshot as `std_msgs/msg/String` on:

```text
/vision/tray/unity_state
```

The JSON schema is `fr5.tray.unity_state/v1`. Each valid snapshot contains the current part counts and every stable part's type, physical-order ID, registered tray pixel, camera XYZ, FR5 Base XYZ, and angle. A picked or moved part disappears or changes position after the detector's stability window confirms the new scene. Invalid registration frames are deliberately ignored, so a brief camera or tray-registration dropout does not erase the twin.

## Unity setup

1. Install Unity Robotics ROS-TCP Connector and Newtonsoft JSON.
2. Copy `Assets/Scripts/TrayVisionSynchronizer.cs` into the Unity project.
3. Add it to the tray/digital-twin root object.
4. Set `Base Frame Origin` to the Unity transform representing FR5 Base and map the eight detector part types to their prefabs:
   `black_block`, `long_orange`, `marked_white`, `right_white_brown`, `gpu`, `hbm`, `power_module`, `inductor`.
5. Adjust `Axis Scale` signs and the optional prefab Euler offsets once to match the model axes. Default units are `0.001 Unity metre / robot millimetre` and the default mapping is FR5 `(X,Y,Z)` to Unity `(X,Z,Y)`.
6. Run the ROS-TCP endpoint and then `vision_assembly/run_tray_merged_detection.sh`.

Inspect the live payload without Unity:

```bash
ros2 topic echo /vision/tray/unity_state std_msgs/msg/String --once
```

`CurrentCounts` is exposed by the component for a UI/status panel. Scene objects are named `Vision_<part_type>:<physical index>` and are created, moved, or destroyed only from valid, monotonically newer snapshots.

> 전체 런처 후속: [25개 단계 API 연결](../docs/FR5_FULL_CYCLE_STEP_API_20260908.md). 최신 전달 묶음은 UNITY_ROBOT_STEP_API_FULL_CYCLE_20260908.zip입니다.

> 2026-09-08 로봇 생산 연동 수정: [단일 Pick/Place API 전달 문서](UNITY_ROBOT_STEP_API_HANDOFF_KO_20260908.md)를 사용하세요. 이전 UNITY_ASSEMBLY_CYCLE_API_20260908.zip의 batch start는 생산용에서 제외했습니다. 기존 비전 문서는 아래에 유지합니다.

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


기판 자세와 25개 보정 슬롯의 Unity 동기화 및 요청 API는 [Unity 기판 캘리브레이션 연결 안내](../docs/UNITY_BOARD_CALIBRATION_API_KO.md)를 참고한다. 기존 Vision Action 계약은 유지된다.

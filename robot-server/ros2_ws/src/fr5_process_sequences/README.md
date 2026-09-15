# FR5 Real robot operation API

This package contains a transport-neutral, fail-closed Real backend and its ROS
2 adapter. It does not read Sequencer YAML or a database.

## Public ROS contract

- command: `/real/robot/command`, `std_msgs/msg/String` containing one JSON operation
- event callback: `/real/robot/event`, `std_msgs/msg/String` containing one JSON event
- pause request: `/real/robot/pause`, `std_msgs/msg/Bool`
- Ghost target: `/real/ghost/target`, `sensor_msgs/msg/JointState`
- internal Vision target: `/real/vision/targets`, `std_msgs/msg/String`

`enable_hardware_execution` defaults to `false`. In that state every valid
operation returns `SAFETY_STOP` and no FR5 motion/gripper command is sent.

## Execution guarantees

1. The command schema and backend-owned process bounds are checked first.
2. Pick/Place/Transfer targets are obtained from fresh backend Vision output.
3. Every Cartesian arm target is solved with referenced IK before the first
   operation motion is sent.
4. Any target/transform/IK failure prevents all operation motion.
5. Immediately before each arm command, final J1..J6 radians are published to
   Ghost. Gripper commands do not publish Ghost targets.
6. `robot_motion_done`, target pose/joints, faults, safety state, timeout, and
   gripper completion are checked before the next phase.
7. Pick and Place are correlated by job, part, slot, and order.
8. Re-delivery of a completed `operation_id` does not repeat physical motion.

## Backend-owned Vision target schema

The currently deployed coarse Vision topics do not contain all calibrated TCP
grasp/place offsets. They must not be converted directly into Real motion. A
commissioned backend Vision component must publish fresh internal targets:

```json
{
  "schema": "fr5.real.vision_targets/v1",
  "timestamp_ros_ns": 123456789,
  "valid": true,
  "coordinate_frame": "base_link",
  "parts": [
    {"part_id":"HBM","order":1,"tcp_pose_mm_deg":[100,200,10,180,0,90]}
  ],
  "slots": [
    {"part_id":"HBM","order":1,"slot_code":"HBM-01","tcp_pose_mm_deg":[50,-500,90,180,0,0]}
  ],
  "transfers": [
    {
      "object_id":"assembled_pcb",
      "pickup_tcp_pose_mm_deg":[0,0,0,180,0,0],
      "drop_tcp_pose_mm_deg":[300,0,0,180,0,0]
    }
  ]
}
```

This is an internal Backend interface, not a Sequencer coordinate interface.

## Important limitation

FR5 `robot_motion_done` and `grip_motion_done` prove controller completion, not
that a part was physically captured or seated. The API currently reports the
minimum requested controller-level completion. Production commissioning still
requires post-grasp and post-placement physical verification; otherwise a
missed pick can still produce `OPERATION_COMPLETED`.

## Start disarmed

```bash
ros2 run fr5_process_sequences real_robot_api
```

The local PC launcher reads `KSMC_REAL_HARDWARE_EXECUTION` from `config/ksmc.env`
(default `false`). The operator enabled it on this PC on 2026-09-08. Restart the
API after changing it: a runtime parameter change alone does not update the
RobotPort. Verify `/real/robot/status.hardware_execution_enabled`. Vision targets,
robot health, referenced IK and joint-path checks still gate each operation;
hardware enablement alone does not commission a physical path.

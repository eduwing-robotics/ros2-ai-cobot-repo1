# FR5 Functional Refactor Checklist

Baseline commit: `7b19fb4 chore: snapshot before FR5 architecture refactor`

## Target tree

```text
FR5/
├── FR5SystemOrchestrator.cs
├── Robot_Control/
│   ├── RobotControlOrchestrator.cs
│   ├── JointController.cs
│   ├── JointDrive.cs
│   └── GripperController.cs
├── Robot_Data/
│   ├── RobotTrajectory.cs
│   └── JointSpecification.cs
├── ROS_Communication/
│   ├── RosCommunicationOrchestrator.cs
│   ├── PlanningAdapter.cs
│   ├── ExecutionAdapter.cs
│   └── GripperCommandAdapter.cs
├── Pick_Place/
│   ├── PickPlaceOrchestrator.cs
│   ├── TargetSelection.cs
│   ├── MotionPlanning.cs
│   └── MotionExecution.cs
├── Operation_View/
│   ├── TrajectoryPreview.cs
│   └── CameraSelector.cs
├── Safety_Monitoring/
│   └── SafetyMonitor.cs
├── Inspector_Tools/
└── System_Tests/
    └── Editor/  # Unity Editor assembly boundary, not a functional layer
```

## Implementation checklist

- [x] Commit the pre-refactor workspace state.
- [x] Create the flat functional folders and preserve Unity `.meta` GUIDs while moving files.
- [x] Keep `FR5` only on the root `FR5SystemOrchestrator`; remove it from subordinate runtime types.
- [x] Give every type a functional namespace matching its folder.
- [x] Replace `RuntimeMaster` and `WorkOrchestrator` with explicit system and Pick & Place orchestration roles.
- [x] Make `RobotControlOrchestrator` the only cross-feature entry point for arm and gripper control.
- [x] Make `RosCommunicationOrchestrator` own ROS connection configuration and `/joint_states` subscription.
- [x] Remove the duplicate gripper `/joint_states` subscriber.
- [x] Keep planning, execution, and gripper transport details in focused ROS adapters.
- [x] Introduce ROS-independent `Robot_Data` contracts.
- [x] Remove ROS message types from Pick & Place and operation-view code.
- [x] Reduce `SafetyMonitor` to validation, health, timeout, and stop notification.
- [x] Route cross-feature commands and events through `FR5SystemOrchestrator`.
- [x] Update custom inspectors to target the renamed entry points.
- [x] Update the URDF importer and builders for renamed control types.
- [x] Rename the importer coordinator from `ImportMaster` to `UrdfImportOrchestrator`.
- [x] Update tests for new names, namespaces, and trajectory model.
- [x] Update Scene serialized class identifiers and remove deleted components.
- [x] Add `<summary>` documentation to public orchestration, state, and boundary APIs.

## Verification checklist

- [x] No old `FR5RuntimeMaster`, `FR5WorkOrchestrator`, `FR5RobotController`, or `FR5Watchdog` code/Scene references remain.
- [x] No subordinate runtime type name starts with `FR5`.
- [x] No `RosMessageTypes` usage exists outside `ROS_Communication` and tests that verify adapters.
- [x] No runtime script imports `UnityEditor` except code guarded by `UNITY_EDITOR`.
- [x] Every moved `.cs` file still has its original `.meta` GUID.
- [x] `SampleScene.unity` loads with zero missing-script component references.
- [x] The URDF importer creates `JointController`, `JointDrive`, `GripperController`, and `RobotControlOrchestrator` correctly.
- [x] Static dependency scan matches the documented reference direction.
- [x] Unity runtime and Editor assemblies compile without C# errors.
- [x] All EditMode tests pass.
- [x] Manual control/import test entry remains available and passes.
- [x] Final `git diff --check` passes.
- [x] Git status contains the intended refactor; unrelated `Assets/Texture` files remain untouched.

## Verification evidence

- Unity 6000.3.21f1 EditMode: 4 passed, 0 failed.
- `SampleSceneHasNoMissingScripts`: passed after loading the real Scene.
- `JointControlTests.Run`: logged `FR5 joint control tests passed.`
- Unity Roslyn compile: `Assembly-CSharp` and `Assembly-CSharp-Editor` passed.
- Script/meta GUID comparison: all moved pairs matched the baseline commit.

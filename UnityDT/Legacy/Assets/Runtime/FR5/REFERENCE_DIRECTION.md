# FR5 Reference Direction

## Rule

Commands travel downward through owned references. Results travel upward through events or read-only state.

```text
FR5SystemOrchestrator
        │ commands and configuration
        ▼
Functional Orchestrator
        │ focused commands
        ▼
Leaf component

Leaf component
        │ events and read-only state
        ▼
Functional Orchestrator
        │ events and aggregate state
        ▼
FR5SystemOrchestrator
```

## Allowed references

1. `FR5SystemOrchestrator` may reference every functional Orchestrator and top-level leaf feature.
2. A functional Orchestrator may reference leaf components inside its own functional folder.
3. A leaf component must not store a reference to its parent Orchestrator.
4. Sibling functional groups share immutable contracts only through `Robot_Data`.
5. `FR5SystemOrchestrator` wires sibling groups with events and method delegates.
6. ROS-generated types must remain inside `ROS_Communication`.
7. `TrajectoryPreview` may drive a separately assigned preview-only `RobotControlOrchestrator`; it must never target the live robot control instance.
8. `System_Tests/Editor` is a Unity compilation boundary, not an additional functional layer.

## Runtime wiring

```text
ROS joint state event
    → FR5SystemOrchestrator
    → SafetyMonitor validation
    → RobotControlOrchestrator pose follow

PickPlaceOrchestrator plan request
    → FR5SystemOrchestrator
    → RosCommunicationOrchestrator
    → PlanningAdapter

PlanningAdapter result
    → RosCommunicationOrchestrator event
    → FR5SystemOrchestrator
    → PickPlaceOrchestrator

SafetyMonitor stop event
    → FR5SystemOrchestrator
    → PickPlaceOrchestrator stop
    → RobotControlOrchestrator stop
```

`Robot_Data` contains values only. It has no Unity scene reference, ROS message, control command, or feature dependency. All other feature groups may depend on it.

## Orchestrator rule

An `Orchestrator` exists only when a class coordinates at least two meaningful subordinate behaviors. It may sequence, route, aggregate, and enforce group-level preconditions. It must delegate parsing, physics, interpolation, transport conversion, and other leaf behavior.

"""AssemblySequencer ROS2 process package."""


CONVEYOR_REMOTE_API = {
    "state_topic": "/conveyor/state",
    "moving_topic": "/conveyor/moving",
    "stop_service": "/conveyor/stop",
    "reset_service": "/conveyor/reset",
    "stations": {
        "ASSEMBLY": {
            "move_service": "/conveyor/move_to_assembly",
            "completed_state": "ASSEMBLY_STOP",
        },
        "INSPECTION": {
            "move_service": "/conveyor/move_to_inspection",
            "completed_state": "INSPECTION_STOP",
        },
    },
}

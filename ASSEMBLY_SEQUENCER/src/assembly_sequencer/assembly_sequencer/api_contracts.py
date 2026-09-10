"""Real consumer declarations; execution and validation belong to RealBackend.

Wire identifiers retain provider versions. No legacy fallback or runtime registry.
Durations are client observation limits, not equipment safety settings.
"""

ROBOT_STATUS = '/real/robot/status'
ASSEMBLY_STATUS = '/real/assembly/status'
ASSEMBLY_COMMAND = '/real/assembly/command'
ASSEMBLY_EVENT = '/real/assembly/event'
CONVEYOR_STATE = '/conveyor/state'
CONVEYOR_ASSEMBLY = '/conveyor/move_to_assembly'
CONVEYOR_INSPECTION = '/conveyor/move_to_inspection'
CONVEYOR_STOP = '/conveyor/stop'
ASSEMBLY_SCHEMA = 'fr5.assembly_execution/v2'
VISION_INSPECTIONS = '/api/v1/inspections'
CONVEYOR_SCHEMA_VERSION = 1
SERVICE_TIMEOUT_SECONDS = 5.0
CONVEYOR_FRESHNESS_SECONDS = 1.0
WAIT_TICK_SECONDS = 0.1
CONVEYOR_TIMEOUT_SECONDS = 35.0
CONTROL_TIMEOUT_SECONDS = 60.0
ASSEMBLY_TIMEOUT_SECONDS = 1800.0
ASSEMBLY_POLL_SECONDS = 2.0
VISION_TIMEOUT_SECONDS = 330.0
VISION_REQUEST_TIMEOUT_SECONDS = 10.0
VISION_POLL_SECONDS = 1.0

#!/usr/bin/env bash
set -euo pipefail

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ros2를 찾을 수 없습니다. ROS 2 Jazzy와 이 workspace의 install/setup.bash를 source하세요." >&2
  exit 2
fi

if [[ "${ROS_DOMAIN_ID:-}" != "5" ]]; then
  echo "ROS_DOMAIN_ID=5가 필요합니다 (현재: ${ROS_DOMAIN_ID:-unset})." >&2
  exit 2
fi

uuid_re='^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'

usage() {
  cat <<'EOF'
사용법: direct_api_test.sh COMMAND [ARGS]

조회(물리 동작 없음):
  endpoints
  conveyor-state
  vision-health
  vision-get INSPECTION_UUID
  vision-image INSPECTION_UUID [SLOT_CODE] [OFFSET]

송신(설비 동작 가능):
  conveyor-assembly
  conveyor-inspection
  conveyor-stop
  conveyor-reset
  vision-submit INSPECTION_UUID JOB_UUID UNIT_ID

주의: conveyor-* 이동 명령은 실제 벨트를 움직일 수 있습니다.
EOF
}

require_uuid() {
  local value="$1" label="$2"
  if [[ ! "$value" =~ $uuid_re ]]; then
    echo "$label 값은 UUID 형식이어야 합니다: $value" >&2
    exit 2
  fi
}

command_name="${1:-}"
case "$command_name" in
  endpoints)
    ros2 service list -t | grep -E '^/(conveyor|vision/inspection)/' || true
    ros2 topic list -t | grep -E '^/(conveyor|vision/conveyor)/' || true
    ;;
  conveyor-state)
    ros2 topic echo --once --field data /conveyor/state std_msgs/msg/String
    ;;
  vision-health)
    ros2 service call /vision/inspection/health std_srvs/srv/Trigger '{}'
    ;;
  conveyor-assembly)
    ros2 service call /conveyor/move_to_assembly std_srvs/srv/Trigger '{}'
    ;;
  conveyor-inspection)
    ros2 service call /conveyor/move_to_inspection std_srvs/srv/Trigger '{}'
    ;;
  conveyor-stop)
    ros2 service call /conveyor/stop std_srvs/srv/Trigger '{}'
    ;;
  conveyor-reset)
    ros2 service call /conveyor/reset std_srvs/srv/Trigger '{}'
    ;;
  vision-submit)
    [[ $# -eq 4 ]] || { usage >&2; exit 2; }
    require_uuid "$2" inspection_id
    require_uuid "$3" job_id
    [[ "$4" =~ ^[1-9][0-9]*$ ]] || { echo "UNIT_ID는 양의 정수여야 합니다." >&2; exit 2; }
    ros2 service call /vision/inspection/submit vision_interfaces/srv/SubmitInspection \
      "{inspection_id: '$2', job_id: '$3', unit_id: $4}"
    ;;
  vision-get)
    [[ $# -eq 2 ]] || { usage >&2; exit 2; }
    require_uuid "$2" inspection_id
    ros2 service call /vision/inspection/get vision_interfaces/srv/GetInspection \
      "{inspection_id: '$2'}"
    ;;
  vision-image)
    [[ $# -ge 2 && $# -le 4 ]] || { usage >&2; exit 2; }
    require_uuid "$2" inspection_id
    slot_code="${3:-}"
    offset="${4:-0}"
    [[ "$offset" =~ ^[0-9]+$ ]] || { echo "OFFSET은 0 이상의 정수여야 합니다." >&2; exit 2; }
    [[ "$slot_code" =~ ^[A-Za-z0-9_-]*$ ]] || { echo "SLOT_CODE 형식이 올바르지 않습니다." >&2; exit 2; }
    ros2 service call /vision/inspection/get_image vision_interfaces/srv/GetInspectionImage \
      "{inspection_id: '$2', slot_code: '$slot_code', offset: $offset, max_bytes: 65536}"
    ;;
  -h|--help|help|'')
    usage
    ;;
  *)
    echo "알 수 없는 명령: $command_name" >&2
    usage >&2
    exit 2
    ;;
esac

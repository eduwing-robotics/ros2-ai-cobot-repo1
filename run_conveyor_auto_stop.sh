#!/usr/bin/env bash
set -Eeo pipefail

# 사용 전 준비:
# 1. TurtleBot에서 robot.launch.py를 실행한다 (ROS_DOMAIN_ID=5).
# 2. 노트북의 다른 터미널에서 ~/KSMC/run_s22_conveyor.sh를 실행한다.
# 3. 기판을 선택한 정지선의 상류에 놓는다.
# 4. 조립 위치로 보낼 때:
#      ~/KSMC/run_conveyor_to_assembly.sh
# 5. 조립 완료 후 검사 위치로 보낼 때:
#      ~/KSMC/run_conveyor_to_inspection.sh
#
# 동작:
# - 실제 벨트의 전진 방향에 맞춰 TurtleBot 기준 후진(-X)으로 0.10 m/s 구동한다.
# - --station assembly/inspection으로 선택한 정지선에서 자동 정지한다.
# - 각 이동은 한 정지선까지만 담당한다. 조립 완료 확인 없이 검사선까지
#   자동 재시작하지 않는다.
# - Ctrl+C 또는 카메라 heartbeat 단절 시에도 정지한다.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STATION="assembly"
if [[ "${1:-}" == "--station" ]]; then
  if [[ $# -lt 2 ]]; then
    echo 'Usage: run_conveyor_auto_stop.sh --station assembly|inspection' >&2
    exit 2
  fi
  STATION="$2"
  shift 2
fi
if [[ "${STATION}" != "assembly" && "${STATION}" != "inspection" ]]; then
  echo "Invalid station: ${STATION} (use assembly or inspection)" >&2
  exit 2
fi

exec "${PROJECT_DIR}/ros2_ws/run_conveyor_stop_test.sh" \
  --station "${STATION}" \
  --cmd-topic /cmd_vel \
  --cmd-type twist_stamped \
  --speed 0.10 \
  --direction negative_x \
  --timeout 0 \
  --execute \
  --confirm-motion \
  "$@"

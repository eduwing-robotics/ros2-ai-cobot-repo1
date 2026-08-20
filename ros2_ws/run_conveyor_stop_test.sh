#!/usr/bin/env bash
set -Eeo pipefail

# 일반 실행은 긴 옵션 대신 다음 래퍼를 사용한다.
#   ~/KSMC/run_conveyor_auto_stop.sh
#
# 이 파일을 직접 사용할 때의 예:
#   ~/KSMC/ros2_ws/run_conveyor_stop_test.sh \
#     --station assembly \
#     --cmd-topic /cmd_vel --cmd-type twist_stamped \
#     --speed 0.10 --direction negative_x \
#     --timeout 0 --execute --confirm-motion

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"

exec ros2 run vision_server conveyor_controller "$@"

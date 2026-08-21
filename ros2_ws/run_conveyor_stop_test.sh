#!/usr/bin/env bash
set -Eeo pipefail

# 일반 실행은 긴 옵션 대신 다음 래퍼를 사용한다.
#   /home/juchan-yoon/FR5_robot_control/run_conveyor_auto_stop.sh
#
# 이 파일을 직접 사용할 때의 예:
#   /home/juchan-yoon/FR5_robot_control/ros2_ws/run_conveyor_stop_test.sh \
#     --cmd-topic /cmd_vel --cmd-type twist_stamped \
#     --speed 0.10 --timeout 0 --execute --confirm-motion

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../scripts/ksmc_env.sh"

exec ros2 run vision_server conveyor_controller "$@"

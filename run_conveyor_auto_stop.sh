#!/usr/bin/env bash
set -Eeo pipefail

# 사용 전 준비:
# 1. TurtleBot에서 robot.launch.py를 실행한다 (ROS_DOMAIN_ID=5).
# 2. 노트북의 다른 터미널에서 ~/KSMC/run_s22_conveyor.sh를 실행한다.
# 3. 기판을 초록 정지선 왼쪽에 놓는다.
# 4. 이 파일을 실행한다:
#      ~/KSMC/run_conveyor_auto_stop.sh
#
# 동작:
# - TurtleBot 바퀴를 0.10 m/s로 계속 구동한다.
# - S22가 기판 후단의 초록선 통과를 검출하면 자동 정지한다.
# - Ctrl+C 또는 카메라 heartbeat 단절 시에도 정지한다.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "${PROJECT_DIR}/ros2_ws/run_conveyor_stop_test.sh" \
  --cmd-topic /cmd_vel \
  --cmd-type twist_stamped \
  --speed 0.10 \
  --timeout 0 \
  --execute \
  --confirm-motion

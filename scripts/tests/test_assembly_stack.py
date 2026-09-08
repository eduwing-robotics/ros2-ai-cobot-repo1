"""Exercise supervisor failure paths with stubbed commands, never robot services."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "run_fr5_assembly_stack.sh"


def run_functions(tmp_path, body):
    source = SCRIPT.read_text().split('command="${1:-}"')[0]
    source = source.replace('source "${root}/scripts/ksmc_env.sh"', 'export ROS_DOMAIN_ID=5')
    script = tmp_path / "supervisor.sh"
    # GUI startup is separate from the supervisor paths exercised here.
    script.write_text(source + "\nstart_phone_view() { :; }\n" + body)
    return subprocess.run(["bash", str(script)], text=True, capture_output=True)


def test_missing_state_is_clear_failure(tmp_path):
    result = run_functions(tmp_path, '''
show_status() { :; }
timeout() { echo "WARNING: topic not published"; }
check_stack
''')
    assert result.returncode == 1
    assert "No valid /nonrt_state_data" in result.stderr


def test_failed_stop_gate_does_not_cleanup_existing_services(tmp_path):
    result = run_functions(tmp_path, '''
endpoint_root="$(dirname "$0")"
printf '#!/bin/bash\\n' > "$endpoint_root/run_with_fairino.sh"
chmod +x "$endpoint_root/run_with_fairino.sh"
preflight_stack() { :; }
assert_safe_to_stop_driver() { return 1; }
stop_managed() { echo UNEXPECTED_STOP; }
start_stack
''')
    assert result.returncode == 1
    assert "UNEXPECTED_STOP" not in result.stdout


def test_driver_without_state_refuses_cleanup(tmp_path):
    result = run_functions(tmp_path, '''
matching_duplicate_pids() { echo 12345; }
timeout() { :; }
pgrep() { return 0; }
assert_safe_to_stop_driver
''')
    assert result.returncode == 1
    assert "stopped robot state could not be confirmed" in result.stderr


def test_camera_none_preserves_external_camera(tmp_path):
    result = run_functions(tmp_path, '''
camera_profile=none
pgrep() {
  case "$*" in
    *realsense*|*rs_launch*) echo 11111 ;;
    *ros2_cmd_server*) echo 22222 ;;
  esac
}
matching_duplicate_pids
stop_component() { echo "STOP:$1"; }
stop_managed
''')
    assert result.returncode == 0
    assert "11111" not in result.stdout
    assert "22222" in result.stdout
    assert "STOP:camera" not in result.stdout
    assert "STOP:unity_fairino" in result.stdout


def test_view_without_desktop_reports_reason(tmp_path):
    result = run_functions(tmp_path, '''
unset DISPLAY WAYLAND_DISPLAY
show_view
''')
    assert result.returncode == 1
    assert "desktop session" in result.stderr


def test_moving_robot_refuses_cleanup(tmp_path):
    result = run_functions(tmp_path, '''
matching_duplicate_pids() { echo 12345; }
timeout() { echo "robot_motion_done: 0"; }
pgrep() { return 0; }
assert_safe_to_stop_driver
''')
    assert result.returncode == 1


def test_stopped_robot_allows_gate(tmp_path):
    result = run_functions(tmp_path, '''
matching_duplicate_pids() { echo 12345; }
timeout() { echo "robot_motion_done: 1"; }
pgrep() { return 0; }
assert_safe_to_stop_driver
''')
    assert result.returncode == 0


def test_view_consumes_full_topic_info_before_launch(tmp_path):
    # A PATH stub also services exec, so no GUI or ROS process is started.
    stub = tmp_path / "ros2"
    stub.write_text("""#!/usr/bin/env python3
import sys
if sys.argv[1:3] == ['pkg', 'prefix']:
    print('/fake/rqt')
elif sys.argv[1:3] == ['topic', 'info']:
    print('Publisher count: 1', flush=True)
    print('Subscription count: 0\\n' * 10000)
elif sys.argv[1] == 'run':
    print('RQT_STUB_LAUNCHED')
""")
    stub.chmod(0o755)
    result = run_functions(tmp_path, '''
export DISPLAY=:0
export PATH="$(dirname "$0"):$PATH"
show_view
''')
    assert result.returncode == 0, result.stderr
    assert "RQT_STUB_LAUNCHED" in result.stdout


def test_view_rejects_zero_publishers(tmp_path):
    result = run_functions(tmp_path, '''
export DISPLAY=:0
ros2() {
  if [[ "$1" == pkg ]]; then return 0; fi
  echo "Publisher count: 0"
}
show_view
''')
    assert result.returncode == 1
    assert "No assembly image publisher" in result.stderr


def test_api_start_does_not_restart_driver_or_other_services(tmp_path):
    result = run_functions(tmp_path, '''
ros2() { return 0; }
start_component() { echo "START:$1"; }
wait_for_node() { :; }
stop_managed() { echo UNEXPECTED_STOP; }
clean_duplicates() { echo UNEXPECTED_CLEAN; }
start_robot_api
''')
    assert result.returncode == 0
    assert 'START:robot_api' in result.stdout
    assert 'DISARMED' in result.stdout
    assert 'UNEXPECTED' not in result.stdout


def test_api_start_preserves_existing_api(tmp_path):
    result = run_functions(tmp_path, '''
ros2() { echo /real_robot_api; }
start_component() { echo UNEXPECTED_START; }
start_robot_api
''')
    assert result.returncode == 0
    assert 'already running' in result.stdout
    assert 'UNEXPECTED_START' not in result.stdout

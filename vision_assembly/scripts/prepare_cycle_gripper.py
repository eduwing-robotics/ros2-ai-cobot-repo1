#!/usr/bin/env python3
"""Execute-only startup under the launcher's actuator lock; never opens/closes jaws."""
import argparse
import json
import time
import rclpy
from std_srvs.srv import Trigger
from fairino_msgs.srv import RemoteCmdInterface
from check_step_api import validate_status


def prepare(status, command, clock=time.monotonic, sleep=time.sleep):
    def safe_state():
        state = status()
        # Only activation may be missing during preparation. All other readiness
        # requirements still apply, and reported gripper faults are never reset.
        validate_status(dict(state, gripper_feedback_valid=True))
        if state.get('gripperfaultnum', 0) or state.get('grippererro', 0):
            raise RuntimeError('gripper fault before activation')
        return state

    def activation():
        values = command('GetGripperActivateStatus()').split(',')
        if len(values) != 3 or int(values[0]) != 0 or int(values[1]) != 0:
            raise RuntimeError('gripper activation query failed: ' + ','.join(values))
        return bool(int(values[2]) & 1)

    safe_state()
    activated = False
    if not activation():
        safe_state()
        if command('ActGripper(1,1)').strip() != '0':
            raise RuntimeError('gripper activation command failed')
        activated = True
    deadline = clock() + 8
    stable_since = None
    while clock() < deadline:
        state = safe_state()
        if state.get('gripper_feedback_valid') and activation():
            if stable_since is None:
                stable_since = clock()
            if clock() - stable_since >= 1:
                return dict(activation_sent=activated, feedback_verified=True)
        else:
            stable_since = None
        sleep(.1)
    raise RuntimeError('gripper activation feedback timeout; assembly not started')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--safety-record', required=True)
    args=parser.parse_args()
    from assembly_cycle_launcher import read, write
    safety=read(args.safety_record)
    rclpy.init()
    node = rclpy.create_node('cycle_gripper_startup')
    try:
        status_client = node.create_client(Trigger, '/real/robot/status')
        command_client = node.create_client(RemoteCmdInterface, '/fairino_remote_command_service')
        def call(client, request):
            if not client.wait_for_service(timeout_sec=3):
                raise RuntimeError('gripper startup service unavailable')
            future = client.call_async(request)
            rclpy.spin_until_future_complete(node, future, timeout_sec=3)
            if not future.done() or future.result() is None:
                raise RuntimeError('gripper startup service timeout; outcome unknown')
            return future.result()
        def status():
            response = call(status_client, Trigger.Request())
            if not response.success:
                raise RuntimeError(response.message)
            return json.loads(response.message)
        def command(cmd):
            if cmd == 'ActGripper(1,1)':
                safety['activation_outcome_unknown']=True
                write(args.safety_record,safety)
            return call(command_client, RemoteCmdInterface.Request(cmd_str=cmd)).cmd_res
        result = prepare(status, command)
        safety['activation_outcome_unknown']=False
        write(args.safety_record,safety)
        print(json.dumps(result), flush=True)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

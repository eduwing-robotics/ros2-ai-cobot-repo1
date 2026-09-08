#!/usr/bin/env python3
"""Read-only readiness check; does not send any robot/gripper command."""
import json
import time
import rclpy
from std_srvs.srv import Trigger
from rcl_interfaces.srv import GetParameters


def validate_status(state):
    if (state.get('api_capabilities_revision')!='step-cycle-20260908'
            or not state.get('hardware_execution_enabled') or not state.get('state_fresh')
            or not state.get('robot_health_clear') or state.get('robot_motion_done')!=1
            or state.get('robot_mode')!=0 or state.get('tool_num')!=1 or state.get('work_num')!=0
            or state.get('active_operation') or state.get('recovery_required')
            or state.get('held_candidate') is not None or not state.get('gripper_feedback_valid')):
        raise RuntimeError('API not ready for a new empty-gripper cycle: '+json.dumps(state))


def main():
    rclpy.init();node=rclpy.create_node('cycle_step_api_readiness')
    try:
        client=node.create_client(Trigger,'/real/robot/status')
        if not client.wait_for_service(timeout_sec=5):raise RuntimeError('step API unavailable')
        future=client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(node,future,timeout_sec=5)
        if not future.done() or not future.result().success:raise RuntimeError('API status timeout/failure')
        state=json.loads(future.result().message);validate_status(state)
        if state.get('continuous_transfer_enabled'):
            capability=node.create_client(GetParameters,'/fr_command_server/get_parameters')
            if not capability.wait_for_service(timeout_sec=3):raise RuntimeError('continuous driver unavailable')
            pending=capability.call_async(GetParameters.Request(names=['continuous_movej_revision']))
            rclpy.spin_until_future_complete(node,pending,timeout_sec=3)
            if (not pending.done() or pending.result() is None or len(pending.result().values)!=1
                    or pending.result().values[0].string_value!='per-command-blend-v1'):
                raise RuntimeError('continuous transfer needs the updated running driver')
            state['continuous_driver_revision']='per-command-blend-v1'

        print(json.dumps(state,ensure_ascii=False))
    finally:node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()

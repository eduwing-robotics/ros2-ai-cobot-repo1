#!/usr/bin/env python3
"""Read-only readiness check; does not send any robot/gripper command."""
import json
import time
import rclpy
from std_srvs.srv import Trigger
from rcl_interfaces.srv import GetParameters
from startup_service_client import wait_for_startup_services, call_readonly_service


def validate_status(state):
    if (state.get('api_capabilities_revision')!='step-cycle-20260908'
            or not state.get('hardware_execution_enabled') or not state.get('state_fresh')
            or not state.get('robot_health_clear') or state.get('robot_motion_done')!=1
            or state.get('robot_mode')!=0 or state.get('tool_num')!=1 or state.get('work_num')!=0
            or state.get('gripperfaultnum', 0) or state.get('grippererro', 0)
            or state.get('active_operation') or state.get('recovery_required')
            or state.get('held_candidate') is not None or not state.get('gripper_feedback_valid')):
        raise RuntimeError('API not ready for a new empty-gripper cycle: '+json.dumps(state))


def main():
    rclpy.init();node=rclpy.create_node('cycle_step_api_readiness')
    try:
        client=node.create_client(Trigger,'/real/robot/status')
        deadline=time.monotonic()+35
        wait_for_startup_services((client,))
        response=call_readonly_service(node,client,Trigger.Request(),deadline=deadline)
        if not response.success:raise RuntimeError('API status failure: '+response.message)
        state=json.loads(response.message);validate_status(state)
        if state.get('continuous_transfer_enabled'):
            capability=node.create_client(GetParameters,'/fr_command_server/get_parameters')
            response=call_readonly_service(node,capability,
                GetParameters.Request(names=['continuous_movej_revision']),deadline=deadline)
            if (len(response.values)!=1 or response.values[0].string_value!='per-command-blend-v1'):
                raise RuntimeError('continuous transfer needs the updated running driver')
            state['continuous_driver_revision']='per-command-blend-v1'

        print(json.dumps(state,ensure_ascii=False))
    finally:node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()

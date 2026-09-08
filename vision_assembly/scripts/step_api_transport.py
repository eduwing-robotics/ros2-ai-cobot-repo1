"""Launcher-side transport only: all actuator commands go to the step API."""
import json
import time
from pathlib import Path
from uuid import UUID

import rclpy
from std_msgs.msg import String
from std_srvs.srv import Trigger
from fr5_process_sequences.sequencer_robot_client import RosSequencerRobotClient
from assembly_cycle_launcher import write


class StepApiSession:
    def __init__(self, node, job_id, directory, recipe=None):
        self.node=node;self.job_id=str(UUID(job_id));self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.active=None
        self.client=RosSequencerRobotClient(node,job_id=self.job_id,recipe=recipe)
        self.status_client=node.create_client(Trigger,'/real/robot/status')
        self.targets=node.create_publisher(String,'/real/vision/targets',10)
        self.event_sub=node.create_subscription(String,'/real/robot/event',self.on_event,100)
        self.record={'job_id':self.job_id,'commands':[],'events':[]}
        self.path=self.directory/'api_requests.json'
        if self.path.exists():raise RuntimeError('API request log already exists; never replay a cycle automatically')
        original=self.client._send
        def durable_send(command):
            self.record['commands'].append(dict(command=command,status='intent',requested_unix=time.time()))
            write(self.path,self.record)
            original(command)
        self.client._send=durable_send

    def on_event(self,message):
        event=json.loads(message.data)
        if event.get('job_id') != self.job_id:return
        self.record['events'].append(event)
        write(self.path,self.record)
        print('API '+str(event.get('action'))+' '+str(event.get('phase'))+' '+str(event.get('event')),flush=True)

    def spin_until(self,predicate,timeout,label):
        deadline=time.monotonic()+timeout
        while rclpy.ok() and time.monotonic()<deadline:
            if predicate():return
            rclpy.spin_once(self.node,timeout_sec=.02)
        raise TimeoutError(label)

    def status(self):
        if not self.status_client.wait_for_service(timeout_sec=5):raise RuntimeError('step API status unavailable')
        future=self.status_client.call_async(Trigger.Request())
        self.spin_until(future.done,5,'API status timeout')
        result=future.result()
        if not result.success:raise RuntimeError(result.message)
        return json.loads(result.message)

    def ready(self):
        self.spin_until(lambda:self.client._command_publisher.get_subscription_count()>0,8,'no robot API subscriber')
        state=self.status()
        if (state.get('api_capabilities_revision')!='step-cycle-20260908'
                or not state.get('hardware_execution_enabled') or not state.get('state_fresh')
                or state.get('robot_motion_done')!=1 or state.get('active_operation')
                or state.get('recovery_required')):
            raise RuntimeError('step API is not idle/ready: '+json.dumps(state))
        return state

    def publish_targets(self,payload):
        self.spin_until(lambda:self.targets.get_subscription_count()>0,5,'no precision target subscriber')
        self.targets.publish(String(data=json.dumps(payload,allow_nan=False)))
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if self.status().get('vision_plan_sha256')==payload['plan_sha256']:return
            rclpy.spin_once(self.node,timeout_sec=.05)
        raise TimeoutError('API did not acknowledge prepared precision plan')

    def call(self,method,*args,timeout=600,**kwargs):
        try:
            self.active=method(*args,**kwargs)
            self.spin_until(self.active.done,timeout,'operation outcome unknown; do not advance')
            result=self.active.result()
            self.record['commands'][-1].update(status='completed',result=result)
            write(self.path,self.record)
            self.active=None
            return result
        except BaseException as error:
            self.record['error']=f'{type(error).__name__}: {error}'
            if self.active is None and self.client._inflight is not None:
                self.active=self.client._pending[self.client._inflight][1]
            if self.active is not None and not self.active.done():
                self.client.pause()
                try:self.spin_until(self.active.done,10,'pause terminal outcome unknown')
                except Exception as stop_error:self.record['pause_error']=str(stop_error)
            self.record['outcome_unknown']=self.active is not None and not self.active.done()
            write(self.path,self.record)
            raise

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
from startup_service_client import call_readonly_service
from check_step_api import validate_status
from cycle_pause import clock as cycle_clock, checkpoint as cycle_checkpoint


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

    def spin_until(self,predicate,timeout,label,pause_aware=False):
        clock=cycle_clock if pause_aware else time.monotonic
        deadline=clock()+timeout
        while rclpy.ok() and clock()<deadline:
            if predicate():return
            rclpy.spin_once(self.node,timeout_sec=.02)
        if predicate():return
        raise TimeoutError(label)

    def status(self, *, deadline=None):
        result=call_readonly_service(self.node,self.status_client,Trigger.Request(),deadline=deadline)
        if not result.success:raise RuntimeError(result.message)
        return json.loads(result.message)

    def ready(self):
        cycle_checkpoint(lambda:rclpy.spin_once(self.node,timeout_sec=.02))
        self.spin_until(lambda:self.client._command_publisher.get_subscription_count()>0,15,'no robot API subscriber: /real/robot/command; no motion request sent')
        state=self.status()
        validate_status(state)
        return state

    def publish_targets(self,payload):
        if payload.get('job_id')!=self.job_id or not payload.get('plan_sha256'):
            raise ValueError('prepared plan must belong to this execution and have a hash')
        cycle_checkpoint(lambda:rclpy.spin_once(self.node,timeout_sec=.02))
        self.spin_until(lambda:self.targets.get_subscription_count()>0,15,'no precision target subscriber: /real/vision/targets; no target sent')
        self.targets.publish(String(data=json.dumps(payload,allow_nan=False)))
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            state=self.status(deadline=deadline)
            validate_status(state)
            prepared=state.get('prepared_execution') or {}
            if (state.get('vision_plan_sha256')==payload['plan_sha256']
                    and prepared.get('job_id')==self.job_id):
                return
            rclpy.spin_once(self.node,timeout_sec=min(.05,max(0.,deadline-time.monotonic())))
        raise TimeoutError('API did not acknowledge prepared precision plan for execution '+self.job_id)

    def call(self,method,*args,timeout=600,**kwargs):
        try:
            cycle_checkpoint(lambda:rclpy.spin_once(self.node,timeout_sec=.02))
            self.active=method(*args,**kwargs)
            self.spin_until(self.active.done,timeout,'operation outcome unknown; do not advance',pause_aware=True)
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

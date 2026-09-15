"""Isolated ROS tests: no production domain, robot commands, or physical drivers."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from uuid import uuid4
import pytest
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from std_srvs.srv import Trigger
from std_msgs.msg import String
from fairino_msgs.msg import RobotNonrtState
from fairino_msgs.srv import RemoteCmdInterface
from fr5_process_sequences.real_ros_node import RealRobotApiNode
from fr5_process_sequences.assembly_cycle_api import AssemblyCycleController, SCHEMA

@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.delenv('KSMC_ROOT',raising=False)
    monkeypatch.delenv('KSMC_LOCAL_FEEDBACK_SOCKET',raising=False)
    monkeypatch.setenv('ROS_DOMAIN_ID','117')
    monkeypatch.setenv('ROS_LOCALHOST_ONLY','1')
    rclpy.init(domain_id=117)
    yield
    rclpy.shutdown()

def test_status_and_feedback_continue_during_blocked_command_callback(isolated):
    api=RealRobotApiNode();probe=rclpy.create_node('isolated_probe')
    executor=MultiThreadedExecutor(num_threads=4);executor.add_node(api)
    entered=threading.Event();release=threading.Event()
    def blocked():
        timer.cancel();entered.set();release.wait(8)
    timer=api.create_timer(.1,blocked)
    thread=threading.Thread(target=executor.spin);thread.start()
    try:
        assert entered.wait(2)
        client=probe.create_client(Trigger,'/real/robot/status')
        assert client.wait_for_service(timeout_sec=3)
        future=client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(probe,future,timeout_sec=3)
        assert future.done() and future.result().success
        assert not json.loads(future.result().message)['hardware_execution_enabled']
        pub=probe.create_publisher(RobotNonrtState,'/nonrt_state_data',10)
        end=time.monotonic()+2
        while pub.get_subscription_count()==0 and time.monotonic()<end:time.sleep(.01)
        baseline=api._robot_port._state_sequence
        pub.publish(RobotNonrtState())
        end=time.monotonic()+2
        while api._robot_port._state_sequence==baseline and time.monotonic()<end:time.sleep(.01)
        assert api._robot_port._state_sequence>baseline
        assert not release.is_set()
    finally:
        release.set();executor.shutdown();thread.join();probe.destroy_node();api.destroy_node()

def test_start_subprocess_under_real_locks_survives_one_lost_status_response(isolated,tmp_path):
    root=Path(__file__).resolve().parents[4]
    config=tmp_path/'vision_assembly/config';config.mkdir(parents=True)
    (config/'assembly_launcher_revision.json').write_text(json.dumps({'revision':'test'}))
    worker=tmp_path/'worker.py'
    worker.write_text("""import fcntl,json,pathlib,subprocess,sys
root=pathlib.Path(sys.argv[1]);scripts=pathlib.Path(sys.argv[2]);run_id=sys.argv[3]
runtime=root/'runtime/assembly_cycles';runtime.mkdir(parents=True,exist_ok=True)
directory=runtime/run_id;directory.mkdir()
safety=directory/'startup_safety.json';safety.write_text(json.dumps(dict(execution_id=run_id,assembly_motion_started=False,activation_outcome_unknown=False)))
with (runtime/'launcher.lock').open('a') as a,(runtime/'step_operation.lock').open('a') as b:
 fcntl.flock(a,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(b,fcntl.LOCK_EX|fcntl.LOCK_NB)
 subprocess.run([sys.executable,str(scripts/'prepare_cycle_gripper.py'),'--safety-record',str(safety)],check=True)
(directory/'startup_verified').write_text('no assembly or actuator command')
""")
    node=rclpy.create_node('isolated_start_server');probe=rclpy.create_node('isolated_start_sender')
    status_group=MutuallyExclusiveCallbackGroup();command_group=MutuallyExclusiveCallbackGroup()
    counts={'status':0,'commands':[]};launches=[]
    def status(req,res):
        counts['status']+=1
        if counts['status']==1:time.sleep(3.4)
        res.success=True;res.message=json.dumps(dict(api_capabilities_revision='step-cycle-20260908',hardware_execution_enabled=True,state_fresh=True,robot_health_clear=True,robot_motion_done=1,robot_mode=0,tool_num=1,work_num=0,held_candidate=None,gripper_feedback_valid=True))
        return res
    def command(req,res):
        counts['commands'].append(req.cmd_str)
        res.cmd_res='0,0,1' if req.cmd_str=='GetGripperActivateStatus()' else 'FORBIDDEN'
        return res
    node.create_service(Trigger,'/real/robot/status',status,callback_group=status_group)
    node.create_service(RemoteCmdInterface,'/fairino_remote_command_service',command,callback_group=command_group)
    def popen(args,**kwargs):
        launches.append(args)
        return subprocess.Popen([sys.executable,str(worker),str(tmp_path),str(root/'vision_assembly/scripts'),args[-1]],**kwargs)
    controller=AssemblyCycleController(tmp_path,lambda:None,lambda _:None,popen=popen)
    errors=[]
    def start(msg):
        try:controller.command(json.loads(msg.data))
        except Exception as e:errors.append(str(e))
    node.create_subscription(String,'/isolated/start',start,10)
    executor=MultiThreadedExecutor(num_threads=4);executor.add_node(node)
    thread=threading.Thread(target=executor.spin);thread.start()
    try:
        pub=probe.create_publisher(String,'/isolated/start',10)
        end=time.monotonic()+3
        while pub.get_subscription_count()==0 and time.monotonic()<end:time.sleep(.01)
        run_id=str(uuid4());request=dict(schema=SCHEMA,action='assembly.start',job_id=run_id,operation_id=run_id,recipe_revision='test',confirm_scene_ready=True)
        pub.publish(String(data=json.dumps(request)))
        end=time.monotonic()+30
        while (controller.process is None or controller.process.poll() is None) and time.monotonic()<end:time.sleep(.05)
        assert not errors
        assert controller.process is not None
        assert controller.process.poll()==0, (tmp_path/'runtime/assembly_api'/f'{run_id}.log').read_text()
        assert (tmp_path/'runtime/assembly_cycles'/run_id/'startup_verified').exists()
        assert len(launches)==1 and counts['status']>=2
        assert counts['commands'] and set(counts['commands'])=={'GetGripperActivateStatus()'}
        # Durable replay must not spawn a second process even after the startup probe finishes.
        controller.command(request);assert len(launches)==1
    finally:
        if controller.process is not None and controller.process.poll() is None:
            controller.process.terminate();controller.process.wait(timeout=5)
        if controller.thread is not None:controller.thread.join(timeout=3)
        executor.shutdown();thread.join();probe.destroy_node();node.destroy_node()


@pytest.mark.parametrize('phase',['PlaceCamera','non-smd','smd'])
def test_real_step_session_readiness_and_plan_ack_retry_without_motion(isolated,tmp_path,phase):
    root=Path(__file__).resolve().parents[4]
    sys.path.insert(0,str(root/'vision_assembly/scripts'))
    from step_api_transport import StepApiSession
    node=rclpy.create_node('isolated_step_server');probe=rclpy.create_node('isolated_step_client')
    requests=[];targets=[];queries=[0];prepared=[None]
    def status(req,res):
        queries[0]+=1
        if queries[0]==1:time.sleep(3.4)
        data=dict(api_capabilities_revision='step-cycle-20260908',hardware_execution_enabled=True,
            state_fresh=True,robot_health_clear=True,robot_motion_done=1,robot_mode=0,
            tool_num=1,work_num=0,held_candidate=None,gripper_feedback_valid=True)
        if prepared[0] is not None:
            data.update(vision_plan_sha256=prepared[0]['plan_sha256'],prepared_execution={'job_id':prepared[0]['job_id']})
        res.success=True;res.message=json.dumps(data);return res
    def receive_target(msg):targets.append(json.loads(msg.data));prepared[0]=targets[-1]
    node.create_service(Trigger,'/real/robot/status',status)
    node.create_subscription(String,'/real/robot/command',lambda msg:requests.append(msg.data),10)
    node.create_subscription(String,'/real/vision/targets',receive_target,10)
    executor=MultiThreadedExecutor(num_threads=4);executor.add_node(node)
    thread=threading.Thread(target=executor.spin);thread.start()
    try:
        job=str(uuid4());session=StepApiSession(probe,job,tmp_path/phase)
        session.ready()
        assert queries[0]>=2
        session.publish_targets({'job_id':job,'plan_sha256':phase+'-hash'})
        assert len(targets)==1 and targets[0]['job_id']==job
        assert not requests and not session.record['commands']
    finally:
        executor.shutdown();thread.join();probe.destroy_node();node.destroy_node()

"""Unity calibration request/reply and board preview. No motion command client."""
from collections import OrderedDict
import json
from pathlib import Path
import time
from uuid import uuid4

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from std_msgs.msg import String, Bool
from fairino_msgs.msg import RobotNonrtState
from .config_utils import default_path, load_yaml
from .conveyor_stop_lease import ConveyorStopLease
from .orchestration_contract import ContractFailure
from .unity_calibration_contract import board_state, tray_state, BoardWindow


class UnityCalibrationServer(Node):
    def __init__(self):
        super().__init__('unity_calibration_api')
        self.declare_parameter('project_root','')
        self.declare_parameter('contract_config',default_path('config/orchestration_api.yaml'))
        root = Path(self.get_parameter('project_root').value)
        if not root.is_absolute():
            raise RuntimeError('absolute project_root parameter required')
        self.config = load_yaml(self.get_parameter('contract_config').value)['orchestration_api']
        def read(relative): return json.loads((root/relative).read_text())
        self.geometry=dict(board=read('vision_assembly/config/physical_board.json'),
            slots=read('vision_assembly/config/assembly_slots_r1.json'),
            residual=read('vision_assembly/config/assembly_placecamera_residual.json'))
        self.layout=read('vision_assembly/config/tray_layout_candidate.json')
        self.references=read('vision_assembly/checkpoints/full_cycle_success_20260906/runtime.json')['teaching_points']
        self.publisher_id=str(uuid4()); self.sequence=0
        self.window=BoardWindow(); self.board=None; self.tray=None; self.robot=None
        self.robot_received=0.; self.view_since={}
        self.conveyor_lease=ConveyorStopLease(
            self.config['pcb'].get('conveyor_heartbeat_max_age_sec',1.0))
        self.pending={}; self.completed=OrderedDict()
        qos=QoSProfile(depth=1,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.preview=self.create_publisher(String,'/vision/board/unity_state',qos)
        self.reply=self.create_publisher(String,'/vision/unity/response',10)
        self.create_subscription(String,self.config['topics']['pcb_state'],lambda m:self._source(m,'board'),10)
        self.create_subscription(String,self.config['topics']['tray_state'],lambda m:self._source(m,'tray'),10)
        self.create_subscription(RobotNonrtState,'/nonrt_state_data',self._robot,10)
        stopped_qos=QoSProfile(depth=1,reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE)
        self.create_subscription(Bool,self.config['topics']['conveyor_stopped'],self._conveyor,stopped_qos)
        self.create_subscription(String,'/vision/unity/request',self._request,10)
        self.create_timer(.2,self._tick)
        self.get_logger().info('Unity board/tray calibration API ready; no robot/conveyor command interfaces')

    def _source(self,message,kind):
        try:
            payload=json.loads(message.data)
            if not isinstance(payload,dict):raise ValueError('object required')
        except (ValueError,TypeError):payload=None
        setattr(self,kind,payload)

    def _conveyor(self,message,message_info):
        self.conveyor_lease.observe(bool(message.data),message_info)

    def _robot(self,s):
        self.robot=s;self.robot_received=time.monotonic()
        pose=np.array([s.cart_x_cur_pos,s.cart_y_cur_pos,s.cart_z_cur_pos,
                       s.cart_a_cur_pos,s.cart_b_cur_pos,s.cart_c_cur_pos],float)
        for name in ('PlaceCamera','TrayHome'):
            reference=np.asarray(self.references[name][:6],float)
            delta=(pose[3:]-reference[3:]+180)%360-180
            ready=(int(s.robot_motion_done)==1 and np.isfinite(pose).all()
                   and np.max(abs(pose[:3]-reference[:3]))<=1 and np.max(abs(delta))<=1
                   and int(s.tool_num)==1 and int(s.work_num)==0)
            if ready:self.view_since.setdefault(name,self.get_clock().now().nanoseconds)
            else:self.view_since.pop(name,None)

    def _pose_guard(self,name,payload):
        if self.robot is None or time.monotonic()-self.robot_received>.5:
            self.view_since.clear()
            raise ContractFailure('CAMERA_NOT_READY','fresh robot feedback unavailable')
        since=self.view_since.get(name)
        if since is None:
            raise ContractFailure('CAMERA_POSE_NOT_READY',f'robot must be stationary at {name}; API does not move it')
        if payload is None:
            raise ContractFailure('CAMERA_NOT_READY','no detector payload')
        try:stamp=int(payload.get('timestamp_ros_ns',0))
        except (TypeError,ValueError):stamp=0
        if stamp < since+2_000_000_000:
            raise ContractFailure('DETECTION_TIMEOUT','waiting for a fresh post-arrival frame')

    def _board_snapshot(self):
        self._pose_guard('PlaceCamera',self.board)
        return board_state(self.board,self.config['pcb'],self.geometry,
                           now_ns=self.get_clock().now().nanoseconds)

    def _tray_snapshot(self):
        self._pose_guard('TrayHome',self.tray)
        return tray_state(self.tray,self.config['tray'],self.layout,
                          now_ns=self.get_clock().now().nanoseconds)

    def _request(self,message):
        request={}
        try:
            request=json.loads(message.data)
            if not isinstance(request,dict):raise ValueError('request must be an object')
            for key in ('request_id','job_id','action'):
                if not isinstance(request.get(key),str) or not request[key].strip() or len(request[key])>128:
                    raise ValueError(f'{key} must be a nonempty string up to 128 characters')
            if request['action'] not in ('getTraySnapshot','getBoardSnapshot','calibrateBoard'):
                raise ValueError('unknown action')
            allowed={'request_id','job_id','action','product_code','product_version'}
            if set(request)-allowed:raise ValueError('unexpected request fields')
            if request['action']!='getTraySnapshot':
                for key in ('product_code','product_version'):
                    if request.get(key)!=self.config['pcb']['expected_'+key]:
                        raise ContractFailure('WRONG_PCB',f'{key} does not match configured board')
            key=request['request_id']; fingerprint=json.dumps(request,sort_keys=True)
            if key in self.completed:
                old,response=self.completed[key]
                if old!=fingerprint:raise ValueError('request_id reused with different content')
                self.reply.publish(String(data=json.dumps(response)));return
            if key in self.pending:
                if self.pending[key]['fingerprint']!=fingerprint:raise ValueError('request_id reused with different content')
                return
            if len(self.pending)>=16:raise ValueError('too many pending requests')
            self.pending[key]=dict(request=request,fingerprint=fingerprint,
                after_ns=self.get_clock().now().nanoseconds,
                conveyor_session=self.conveyor_lease.current_session(),
                deadline=time.monotonic()+float(self.config['detection_timeout_sec']))
        except (ValueError,TypeError,ContractFailure) as error:
            self._respond(request if isinstance(request,dict) else {},False,
                          error_code=getattr(error,'code','INVALID_REQUEST'),message=str(error))

    def _respond(self,request,success,*,data=None,error_code='',message=''):
        response=dict(schema='fr5.unity.calibration_response/v1',request_id=request.get('request_id',''),
            job_id=request.get('job_id',''),action=request.get('action',''),success=success,
            error_code=error_code,message=message,data=data,robot_motion_authorized=False)
        self.reply.publish(String(data=json.dumps(response,allow_nan=False)))
        return response

    def _tick(self):
        now_ns=self.get_clock().now().nanoseconds
        state=None;failure=None
        try:
            state=self._board_snapshot();self.window.observe(state)
            state=dict(state,stable=self.window.stable(now_ns=now_ns))
        except (ContractFailure,KeyError,ValueError,TypeError) as error:
            self.window.clear();failure=error
            state=dict(schema='fr5.board.unity_state/v1',valid=False,stable=False,
                error_code=getattr(error,'code','CALIBRATION_NOT_READY'),reason=str(error),
                timestamp_ros_ns=None,robot_motion_authorized=False)
        self.sequence+=1
        self.preview.publish(String(data=json.dumps(dict(state,publisher_id=self.publisher_id,
            sequence=self.sequence,published_ros_ns=now_ns),allow_nan=False)))
        for key,job in list(self.pending.items()):
            request=job['request'];error=failure;data=None
            try:
                if request['action']=='getTraySnapshot':data=self._tray_snapshot()
                else:
                    if request['action']=='calibrateBoard' and self.config['pcb'].get('require_conveyor_stopped',True):
                        session=self.conveyor_lease.current_session()
                        if job['conveyor_session'] is None and session is not None:
                            job['conveyor_session']=session
                            # New stop evidence needs new board observations too.
                            job['after_ns']=now_ns
                        if not self.conveyor_lease.permits(job['conveyor_session']):
                            if job['conveyor_session'] is not None:
                                job['deadline']=0
                            raise ContractFailure('CONVEYOR_NOT_STOPPED',
                                'fresh stopped heartbeat expired, cleared, or publisher session changed')
                    if failure:raise failure
                    after=job['after_ns'] if request['action']=='calibrateBoard' else 0
                    if not self.window.stable(after_ns=after, now_ns=now_ns):
                        raise ContractFailure('UNSTABLE_POSE','four distinct stable board frames required')
                    data=state
            except (ContractFailure,KeyError,ValueError,TypeError) as caught:error=caught
            if data is not None:
                response=self._respond(request,True,data=data)
            elif time.monotonic()>=job['deadline']:
                response=self._respond(request,False,error_code=getattr(error,'code','CALIBRATION_NOT_READY'),message=str(error))
            else:continue
            self.completed[key]=(job['fingerprint'],response)
            if len(self.completed)>128:self.completed.popitem(last=False)
            del self.pending[key]


def main(args=None):
    rclpy.init(args=args);node=UnityCalibrationServer()
    try:rclpy.spin(node)
    except KeyboardInterrupt:pass
    finally:node.destroy_node();rclpy.shutdown()

#!/usr/bin/env python3
"""Bounded RGB sharpness comparison with restoration; sends no robot commands."""
import argparse,json,subprocess,sys,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rcl_interfaces.srv import GetParameters,SetParameters

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
rclpy.init();n=Node('smd_sharpness_comparison')
get=n.create_client(GetParameters,'/camera/camera/get_parameters')
setp=n.create_client(SetParameters,'/camera/camera/set_parameters')
def call(client,request):
    if not client.wait_for_service(timeout_sec=4):raise RuntimeError('camera service unavailable')
    f=client.call_async(request);rclpy.spin_until_future_complete(n,f,timeout_sec=8)
    if not f.done() or f.result() is None:raise RuntimeError('camera parameter timeout')
    return f.result()
key='rgb_camera.sharpness'
def read():return call(get,GetParameters.Request(names=[key])).values[0].integer_value
def change(value):
    reply=call(setp,SetParameters.Request(parameters=[Parameter(key,value=value).to_parameter_msg()]))
    if len(reply.results)!=1 or not reply.results[0].successful:raise RuntimeError(str(reply))
    if read()!=value:raise RuntimeError('sharpness readback mismatch')
original=read();record=dict(original_sharpness=original,robot_motion_authorized=False,runs=[])
(a.output/'experiment.json').write_text(json.dumps(record,indent=2))
scripts=Path(__file__).resolve().parent
try:
    for label,value in [('baseline',original),('off',0),('high',100),('baseline_repeat',original)]:
        change(value)
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:rclpy.spin_once(n,timeout_sec=.1)
        print(f'CAPTURE {label}: sharpness={value}',flush=True)
        dest=a.output/label
        subprocess.run([sys.executable,str(scripts/'diagnose_smd_frame_jitter.py'),
                        '--output',str(dest),'--frames','30'],check=True,timeout=100)
        subprocess.run([sys.executable,str(scripts/'compare_smd_terminal_edges.py'),str(dest)],
                       check=True,timeout=60,stdout=subprocess.DEVNULL)
        record['runs'].append(dict(label=label,sharpness=value,directory=str(dest)))
        (a.output/'experiment.json').write_text(json.dumps(record,indent=2))
finally:
    try:
        change(original);record['restored_sharpness']=read()
        print(f'RESTORED sharpness={record["restored_sharpness"]}',flush=True)
    finally:
        (a.output/'experiment.json').write_text(json.dumps(record,indent=2))
        n.destroy_node();rclpy.shutdown()

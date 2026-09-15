#!/usr/bin/env python3
"""Temporary RGB resolution diagnostic, restores original profile. No arm commands."""
import argparse,json,subprocess,sys,time
from pathlib import Path
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import qos_profile_sensor_data
from rcl_interfaces.srv import GetParameters,SetParameters
from sensor_msgs.msg import Image,CameraInfo

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
rclpy.init();n=Node('smd_resolution_diagnostic');latest={}
get=n.create_client(GetParameters,'/camera/camera/get_parameters');setp=n.create_client(SetParameters,'/camera/camera/set_parameters')
def call(client,request):
    if not client.wait_for_service(timeout_sec=5):raise RuntimeError('camera parameter service absent')
    future=client.call_async(request);rclpy.spin_until_future_complete(n,future,timeout_sec=12)
    if not future.done() or future.result() is None:raise RuntimeError('camera parameter timeout')
    return future.result()
names=['rgb_camera.color_profile','enable_color','depth_module.depth_profile']
values=call(get,GetParameters.Request(names=names)).values
original=values[0].string_value
if not values[1].bool_value:raise RuntimeError('color stream was disabled')
record=dict(original_color_profile=original,original_depth_profile=values[2].string_value,
            diagnostic_only=True,robot_motion_authorized=False,runs=[])
(a.output/'experiment.json').write_text(json.dumps(record,indent=2))
def change(name,value):
    r=call(setp,SetParameters.Request(parameters=[Parameter(name,value=value).to_parameter_msg()]))
    if len(r.results)!=1 or not r.results[0].successful:raise RuntimeError(str(r))
def image_cb(key,m):
    latest[key]=(m.width,m.height,m.header.stamp.sec+m.header.stamp.nanosec/1e9,time.monotonic())
n.create_subscription(Image,'/camera/camera/color/image_raw',lambda m:image_cb('rgb',m),qos_profile_sensor_data)
n.create_subscription(Image,'/camera/camera/aligned_depth_to_color/image_raw',lambda m:image_cb('depth',m),qos_profile_sensor_data)
n.create_subscription(CameraInfo,'/camera/camera/color/camera_info',lambda m:latest.update(info=(m.width,m.height,list(m.k))),qos_profile_sensor_data)
def ready(profile):
    width,height,_=map(int,profile.split('x'));end=time.monotonic()+25;first=None
    while time.monotonic()<end:
        rclpy.spin_once(n,timeout_sec=.1)
        if not all(k in latest for k in ('rgb','depth','info')):continue
        if any(latest[k][:2]!=(width,height) for k in ('rgb','depth','info')):continue
        if any(abs(time.time()-latest[k][2])>1. for k in ('rgb','depth')):continue
        stamps=tuple(latest[k][2] for k in ('rgb','depth'))
        if first is None:first=stamps
        if min(b-a for a,b in zip(first,stamps))>1.:
            return dict(profile=profile,rgb=list(latest['rgb'][:3]),depth=list(latest['depth'][:3]),camera_info=list(latest['info']))
    raise RuntimeError('fresh matching RGB/depth/CameraInfo not received: '+str(latest))
def switch(profile):
    change('enable_color',False)
    change('rgb_camera.color_profile',profile)
    latest.clear()
    change('enable_color',True)
    return ready(profile)
scripts=Path(__file__).resolve().parent
try:
    for label,profile in [('baseline',original),('high','1920x1080x15')]:
        print('PROFILE',label,profile,flush=True)
        status=ready(profile) if label=='baseline' else switch(profile)
        dest=a.output/label
        subprocess.run([sys.executable,str(scripts/'diagnose_smd_frame_jitter.py'),'--output',str(dest),'--frames','30'],check=True,timeout=100)
        subprocess.run([sys.executable,str(scripts/'compare_smd_terminal_edges.py'),str(dest)],check=True,timeout=60,stdout=subprocess.DEVNULL)
        record['runs'].append(dict(label=label,**status))
        (a.output/'experiment.json').write_text(json.dumps(record,indent=2))
finally:
    try:
        record['restored']=switch(original)
        print('RESTORED',json.dumps(record['restored']),flush=True)
    finally:
        (a.output/'experiment.json').write_text(json.dumps(record,indent=2))
        n.destroy_node();rclpy.shutdown()

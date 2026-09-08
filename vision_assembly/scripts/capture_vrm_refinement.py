#!/usr/bin/env python3
"""Read-only TrayHome VRM refinement; write snapshot only after all five pass."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import cv2
import numpy as np
from vrm_edge_refinement import measure, summarize, merge

ROOT=Path(__file__).resolve().parents[2]


def main():
    import rclpy
    from sensor_msgs.msg import CompressedImage, CameraInfo
    from rclpy.qos import qos_profile_sensor_data
    from execute_full_fixed_cycle import Executor, validate_start_state, pose_error, atomic_write
    from fixed_cycle_snapshot import validate_tray_detection_quality
    from tray_home_gate import HOME
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=120)
    args=parser.parse_args()
    directory=args.directory
    snapshot=json.loads((directory/'snapshot.json').read_text())
    expected_hash=hashlib.sha256((ROOT/'calibration/data/handeye_result.json').read_bytes()).hexdigest()
    if snapshot['tray_capture']['handeye_sha256']!=expected_hash:
        raise RuntimeError('VRM refinement handeye changed')
    if not 0<=time.time()-snapshot['tray_capture']['captured_unix']<180:
        raise RuntimeError('VRM refinement needs fresh TrayHome capture')
    coarse={p['instance_index']:p for p in snapshot['tray_capture']['parts'] if p['part_type']=='black_block'}
    if set(coarse)!={1,2,3,4,5}:raise RuntimeError('VRM coarse count mismatch')
    quality=json.loads((ROOT/'vision_assembly/config/part_gripper_recipes.json').read_text())['tray_snapshot_quality']
    rclpy.init();node=Executor();images=[None];infos=[None]
    node.create_subscription(CompressedImage,'/camera/camera/color/image_raw/compressed',lambda m:images.__setitem__(0,m),qos_profile_sensor_data)
    node.create_subscription(CameraInfo,'/camera/camera/color/camera_info',lambda m:infos.__setitem__(0,m),qos_profile_sensor_data)
    samples={i:[] for i in coarse};accepted={};anchors={};reasons={};last=0.;report_at=0.;after=time.time()
    record={'status':'collecting','method':'vrm_four_edge_v1'}
    try:
        deadline=time.monotonic()+args.timeout
        while time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.05)
            if node.state is None or images[0] is None or infos[0] is None:continue
            validate_start_state(node)
            distance,angle=pose_error(node.snapshot(),list(HOME))
            if distance>1 or angle>1:raise RuntimeError('VRM refinement requires stationary TrayHome')
            msg=images[0];stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9;now=time.time()
            if stamp<after or stamp<last+.12 or not 0<=now-stamp<1:continue
            last=stamp
            payload=json.loads((ROOT/'vision_assembly/data/tray_detections_last.json').read_text())
            if not 0<=now-payload['timestamp_ros_ns']/1e9<2:continue
            if payload['handeye_sha256']!=expected_hash:raise RuntimeError('live handeye changed')
            if payload['tray_registration']!='TRACKING' or payload['base_transform_status'] not in ('OK','VALID_COORDINATES_ONLY'):continue
            ds={d['instance_index']:d for d in payload['stable_detections'] if d['part_type']=='black_block'}
            if set(ds)!=set(coarse):continue
            im=cv2.imdecode(np.frombuffer(msg.data,np.uint8),1)
            transform=np.array(payload['T_base_flange'])@np.array(payload['T_flange_camera'])
            for index,d in ds.items():
                # Preserve physical cell identity and refuse changed inventory.
                if np.linalg.norm(np.array(d['reference_center_pixel'])-coarse[index]['reference_center_pixel'])>12:
                    raise RuntimeError(f'VRM-{index:02} cell identity changed')
                if np.linalg.norm(np.array(d['base_xyz_mm'])-coarse[index]['base_xyz_mm'])>2:
                    raise RuntimeError(f'VRM-{index:02} geometry changed since tray capture')
                try:
                    validate_tray_detection_quality(d,quality)
                    result=measure(im,d,infos[0].k,transform)
                    if index in accepted:
                        delta=np.linalg.norm(np.array(result['center_base_mm'])-accepted[index]['base_xyz_mm'])
                        angular=abs(result['base_angle_deg']-accepted[index]['long_axis_angle_base_deg'])
                        if delta>2 or angular>3:raise RuntimeError(f'accepted VRM-{index:02} geometry changed')
                        continue
                    if index not in anchors:anchors[index]=d['base_xyz_mm']
                    if np.linalg.norm(np.array(d['base_xyz_mm'])-anchors[index])>=1.5:
                        raise ValueError('VRM center moved during window')
                    result['timestamp']=stamp;samples[index].append(result)
                    if len(samples[index])==12:
                        accepted[index]=summarize(samples[index]);accepted[index]['refinement_captured_unix']=stamp
                        reasons.pop(index,None)
                except ValueError as exc:
                    samples[index]=[];anchors.pop(index,None);reasons[index]=str(exc)
                except RuntimeError as exc:
                    if 'geometry changed' in str(exc):raise
                    if index not in accepted:samples[index]=[];anchors.pop(index,None)
                    reasons[index]=str(exc)
            record.update(accepted=sorted(accepted),pending={i:reasons.get(i,'collecting frames') for i in coarse if i not in accepted})
            if time.monotonic()-report_at>5:
                print(f'VRM EDGES: {len(accepted)}/5 accepted; pending={record["pending"]}',flush=True)
                atomic_write(directory/'vrm_refinement.json',record);report_at=time.monotonic()
            if len(accepted)==5:
                captured=min(v['refinement_captured_unix'] for v in accepted.values())
                result=merge(snapshot,accepted,captured)
                (directory/'vrm_refinement.jpg').write_bytes(bytes(msg.data))
                record.update(status='validated',refinements=accepted,samples=samples,finished_unix=now)
                atomic_write(directory/'vrm_refinement.json',record)
                atomic_write(directory/'snapshot.json',result)
                print('VRM four-edge centers and axes validated for all five; no robot motion.',flush=True)
                return
        raise RuntimeError(f'VRM refinement timeout: {record.get("pending")}')
    except BaseException as exc:
        record.update(status='failed',error=str(exc));atomic_write(directory/'vrm_refinement.json',record)
        raise
    finally:node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()

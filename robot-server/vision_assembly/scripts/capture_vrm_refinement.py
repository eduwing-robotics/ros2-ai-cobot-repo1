#!/usr/bin/env python3
"""Read-only, synchronized TrayHome refinement with bounded full recapture."""
import argparse
from collections import deque
import hashlib
import json
import time
from pathlib import Path
import cv2
import numpy as np
from tray_set_selection import select_cycle_tray_set
from vrm_edge_refinement import merge
from vrm_refinement_window import VrmRefinementWindow, RecaptureRequired, matched_evidence
from tray_capture_retry import TrayCaptureRetry, RetryCaptureError

ROOT=Path(__file__).resolve().parents[2]
MAX_FULL_RECAPTURES=2


def main():
    import rclpy
    from sensor_msgs.msg import CompressedImage, CameraInfo
    from rclpy.qos import qos_profile_sensor_data
    from execute_full_fixed_cycle import Executor, validate_start_state, pose_error, atomic_write
    from fixed_cycle_snapshot import capture_tray
    from cycle_camera_stage import capture_args
    from tray_home_gate import HOME
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=120)
    args=parser.parse_args();directory=args.directory
    snapshot=json.loads((directory/'snapshot.json').read_text())
    expected_hash=hashlib.sha256((ROOT/'calibration/data/handeye_result.json').read_bytes()).hexdigest()
    if snapshot['tray_capture']['handeye_sha256']!=expected_hash:raise RuntimeError('VRM refinement handeye changed')
    if not 0<=time.time()-snapshot['tray_capture']['captured_unix']<180:raise RuntimeError('VRM refinement needs fresh TrayHome capture')
    quality=json.loads((ROOT/'vision_assembly/config/part_gripper_recipes.json').read_text())['tray_snapshot_quality']
    config=(snapshot['tray_capture'].get('assembly_set_selection') or {}).get('config')
    registration={p.get('tray_registration_id') for p in snapshot['tray_capture']['parts'] if p.get('tray_registration_id')}
    window=VrmRefinementWindow(snapshot,quality)
    rclpy.init();node=Executor();images=deque(maxlen=180);infos=deque(maxlen=180)
    node.create_subscription(CompressedImage,'/camera/camera/color/image_raw/compressed',lambda m:images.append(m),qos_profile_sensor_data)
    node.create_subscription(CameraInfo,'/camera/camera/color/camera_info',lambda m:infos.append(m),qos_profile_sensor_data)
    after=time.time();report_at=0.;last=None;recapture=None
    record={'status':'collecting','method':'vrm_four_edge_v1','evidence_mode':'matched_image_detection_intrinsics','full_recaptures':[]}
    parameters=capture_args(directory);parameters.defer_smd_to_close_view=True
    parameters.tray_input=directory/'vrm_recapture_observation.json'
    try:
        deadline=time.monotonic()+args.timeout
        while time.monotonic()<deadline:
            rclpy.spin_once(node,timeout_sec=.02)
            if node.state is None or not images or not infos:continue
            validate_start_state(node)
            distance,angle=pose_error(node.snapshot(),list(HOME))
            if distance>1 or angle>1:raise RuntimeError('VRM refinement requires stationary TrayHome')
            now=time.time()
            payload=json.loads((ROOT/'vision_assembly/data/tray_detections_last.json').read_text())
            stamp=payload['timestamp_ros_ns']
            if stamp==last:continue
            matched=matched_evidence(images,infos,stamp,after=after,now=now)
            if matched is None:continue
            last=stamp;msg,info=matched
            if payload['handeye_sha256']!=expected_hash:raise RuntimeError('live handeye changed')
            if payload['tray_registration']!='TRACKING' or payload['base_transform_status'] not in ('OK','VALID_COORDINATES_ONLY'):
                raise RuntimeError('tray registration/transform lost during refinement')
            if registration and payload.get('tray_registration_id') not in registration:
                raise RuntimeError('tray registration identity changed during refinement')
            payload=select_cycle_tray_set(payload,config)
            im=cv2.imdecode(np.frombuffer(msg.data,np.uint8),1)
            transform=np.array(payload['T_base_flange'])@np.array(payload['T_flange_camera'])
            try:
                if recapture is not None:
                    if stamp/1e9<=recapture.after:continue
                    refreshed=recapture.observe(payload,now)
                    record['recapture_progress']=recapture.report()
                    if refreshed is not None:
                        atomic_write(parameters.tray_input,refreshed)
                        snapshot=capture_tray(parameters,snapshot)
                        snapshot['tray_capture'].update(captured_unix=refreshed['oldest_part_capture_unix'],
                            per_part_capture_sources=refreshed['per_part_capture_sources'],capture_mode=refreshed['capture_mode'])
                        # All 25 coordinates and all five refinements are replaced together.
                        atomic_write(directory/'vrm_recapture_snapshot.json',snapshot)
                        window=VrmRefinementWindow(snapshot,quality);recapture=None
                        print('FULL TRAY RECAPTURE completed; restarting all five refinements, no motion.',flush=True)
                    complete=False
                else:
                    complete=window.observe(im,payload,info.k,transform)
            except (RecaptureRequired,RetryCaptureError) as error:
                if len(record['full_recaptures'])>=MAX_FULL_RECAPTURES:
                    raise RuntimeError('VRM full recapture limit exhausted: '+str(error)) from error
                record['full_recaptures'].append({'reason':str(error),'started_unix':now})
                atomic_write(directory/'vrm_rejected_observation.json',payload)
                (directory/'vrm_rejected_image.jpg').write_bytes(bytes(msg.data))
                recapture=TrayCaptureRetry(quality,after=now,defer_smd_to_close_view=True)
                window=VrmRefinementWindow(snapshot,quality)
                print('FULL TRAY RECAPTURE: '+str(error),flush=True);complete=False
            record.update(accepted=sorted(window.accepted),pending=window.pending())
            if time.monotonic()-report_at>5:
                print(f'VRM EDGES: {len(window.accepted)}/5 accepted; pending={record["pending"]}',flush=True)
                atomic_write(directory/'vrm_refinement.json',record);report_at=time.monotonic()
            if complete:
                captured=min(v['refinement_captured_unix'] for v in window.accepted.values())
                result=merge(snapshot,window.accepted,captured)
                (directory/'vrm_refinement.jpg').write_bytes(bytes(msg.data))
                record.update(status='validated',refinements=window.accepted,samples=window.samples,finished_unix=now)
                atomic_write(directory/'vrm_refinement.json',record)
                atomic_write(directory/'snapshot.json',result)
                print('VRM four-edge centers and axes validated for all five; no robot motion.',flush=True)
                return
        raise RuntimeError(f'VRM refinement timeout: {record.get("pending")}; recapture={record.get("recapture_progress")}')
    except BaseException as error:
        record.update(status='failed',error=str(error));atomic_write(directory/'vrm_refinement.json',record)
        raise
    finally:node.destroy_node();rclpy.shutdown()


if __name__=='__main__':main()

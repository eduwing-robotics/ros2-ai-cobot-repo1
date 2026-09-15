#!/usr/bin/env python3
"""Freeze a repeatable Base target from a running tray detector output."""

import argparse
import json
import time
from pathlib import Path

import numpy as np


def load_match(path, part_type, instance):
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not str(data.get('tray_registration', '')).startswith('TRACKING') or
            data.get('base_transform_status') != 'VALID_COORDINATES_ONLY'):
        return None
    for item in data.get('stable_detections', []):
        if item.get('part_type') == part_type and int(item.get('instance_index', -1)) == instance:
            xyz = np.asarray(item.get('base_xyz_mm'), dtype=float)
            if xyz.shape == (3,) and np.all(np.isfinite(xyz)):
                return data, item, xyz
    return None


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detection-file', type=Path, default=root/'data/tray_detections_last.json')
    parser.add_argument('--part-type', required=True)
    parser.add_argument('--instance', type=int, default=1)
    parser.add_argument('--frames', type=int, default=5,
                        help='accepted consecutive detector updates; outliers restart collection')
    parser.add_argument('--max-jitter-mm', type=float, default=1.0)
    parser.add_argument('--timeout-sec', type=float, default=45.0)
    parser.add_argument('--output', type=Path, default=root/'data/tray_part_target_last.json')
    args = parser.parse_args()
    if args.frames < 5:
        parser.error('--frames must be at least 5')
    if args.instance < 1 or args.max_jitter_mm <= 0:
        parser.error('invalid instance or jitter limit')
    samples=[];angles=[];last_timestamp=None;last_item=None
    deadline=time.monotonic()+args.timeout_sec
    print(f'FREEZE TRAY TARGET: {args.part_type} #{args.instance}; collecting {args.frames} stable detector updates')
    while time.monotonic()<deadline:
        try:
            result=load_match(args.detection_file,args.part_type,args.instance)
        except (OSError,json.JSONDecodeError):
            result=None
        if result is None:
            time.sleep(.15);continue
        data,item,xyz=result;stamp=data.get('timestamp_unix')
        if stamp==last_timestamp:
            time.sleep(.15);continue
        try:
            base_angle=float(item['long_axis_angle_base_deg'])
        except (KeyError,TypeError,ValueError):
            time.sleep(.15);continue
        last_timestamp=stamp;last_item=item;samples.append(xyz);angles.append(base_angle)
        points=np.asarray(samples);center=np.median(points,axis=0)
        jitter=float(np.max(np.linalg.norm(points-center,axis=1)))
        print(f'Stable target frames: {len(samples)}/{args.frames}; max jitter={jitter:.3f} mm')
        if jitter>args.max_jitter_mm:
            print('Jitter exceeded limit; restarting collection')
            samples=[];angles=[];last_timestamp=None
        elif len(samples)>=args.frames:
            doubled=np.deg2rad(np.asarray(angles,float)*2.0)
            angle_median=.5*np.degrees(np.arctan2(
                np.median(np.sin(doubled)),np.median(np.cos(doubled))))
            output={
                'schema_version':1,'mode':'frozen_tray_part_target',
                'timestamp_unix':time.time(),'part_type':args.part_type,
                'instance_index':args.instance,'display_name':last_item.get('display_name',args.part_type),
                'part_center_base_mm':np.round(center,3).tolist(),
                'long_axis_angle_base_deg':round(float(angle_median),3),
                'sample_count':len(samples),'max_jitter_mm':round(jitter,4),
                'source_detection_file':str(args.detection_file),
                'transform_chain':data.get('transform_chain'),
            }
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
            print('Frozen Base target [mm]:',output['part_center_base_mm'])
            print('Saved:',args.output)
            return
        time.sleep(.1)
    raise RuntimeError('Timed out waiting for a stable tray target; return to the tray view and keep the robot still')


if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""Merge TrayHome SMD XYZ with close-view angle; never moves the robot."""
import argparse,json,math,time
from pathlib import Path
import numpy as np

def main():
 root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser()
 p.add_argument('--coarse',type=Path,required=True);p.add_argument('--fine',type=Path,required=True)
 p.add_argument('--output',type=Path,default=root/'data/smd_merged_target.json')
 p.add_argument('--max-age-sec',type=float,default=300.)
 p.add_argument('--max-coarse-fine-angle-error-deg',type=float,default=5.0);a=p.parse_args()
 coarse=json.loads(a.coarse.read_text());fine_payload=json.loads(a.fine.read_text());now=time.time()
 if fine_payload.get('mode')=='smd_close_multiframe_base_targets':
  if not fine_payload.get('validation_passed'):raise RuntimeError('fine-angle batch validation did not pass')
  instance=int(coarse.get('instance_index',-1))
  matches=[q for q in fine_payload.get('parts',[]) if int(q.get('instance_index',-2))==instance]
  if len(matches)!=1:raise RuntimeError(f'fine-angle batch has {len(matches)} matches for instance {instance}')
  fine=matches[0]
 else:fine=fine_payload
 for name,q in [('coarse',coarse),('fine',fine_payload)]:
  age=now-float(q['timestamp_unix'])
  if age < -5 or age>a.max_age_sec:raise RuntimeError(f'{name} target stale: {age:.1f}s')
 if coarse.get('part_type')!='right_white_brown':raise RuntimeError('coarse target is not SMD')
 if int(coarse.get('instance_index',-1))!=int(fine.get('instance_index',-2)):raise RuntimeError('instance mismatch')
 if not fine.get('validation_passed'):raise RuntimeError('fine-angle validation did not pass')
 xyz=np.asarray(coarse['part_center_base_mm'],float);angle=float(fine['long_axis_angle_base_deg'])
 if xyz.shape!=(3,) or not np.all(np.isfinite(xyz)) or not math.isfinite(angle):raise RuntimeError('invalid merged target')
 coarse_angle=float(coarse['long_axis_angle_base_deg'])
 # TrayHome and close-view axes must agree modulo 180 degrees. A near-90-degree
 # mismatch means one detector selected the perpendicular rectangle axis and
 # must fail closed instead of being used for a grasp.
 expected_close=coarse_angle%180.0
 angle_error=abs((angle-expected_close+90.0)%180.0-90.0)
 if angle_error>a.max_coarse_fine_angle_error_deg:
  raise RuntimeError(
   f'coarse/fine angle contradiction: coarse={coarse_angle:.3f} deg, '
   f'expected close-pick axis={expected_close:.3f} deg, fine={angle:.3f} deg, '
   f'error={angle_error:.3f} deg exceeds {a.max_coarse_fine_angle_error_deg:.3f} deg')
 out={'schema_version':1,'mode':'smd_trayhome_xyz_plus_close_angle','timestamp_unix':now,
  'robot_motion_authorized':False,'part_type':'right_white_brown','display_name':'SMD Capacitor',
  'instance_index':int(coarse['instance_index']),'part_center_base_mm':np.round(xyz,3).tolist(),
  'long_axis_angle_base_deg':round(angle,3),'coarse_fine_angle_error_deg':round(angle_error,3),'position_source':'TrayHome full-tray detection',
  'angle_source':'SMD close-view robust OBB only','coarse_file':str(a.coarse),'fine_file':str(a.fine)}
 a.output.write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()

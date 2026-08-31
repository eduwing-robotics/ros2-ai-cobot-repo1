#!/usr/bin/env python3
"""Non-contact HBM coarse-to-fine eye-in-hand alignment test."""
import argparse,json,subprocess,time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
VISION=ROOT/'vision_assembly'
CAPTURE=VISION/'scripts/capture_single_vrm_hover_target.py'
MOVE=ROOT/'calibration/run_object_approach.sh'
DATA=VISION/'data'

def run(command,label):
 print(f'\n=== {label} ===',flush=True);print(' '.join(map(str,command)),flush=True)
 completed=subprocess.run([str(x) for x in command],check=False)
 if completed.returncode:raise RuntimeError(f'{label} failed: exit={completed.returncode}')

def load(path):return json.loads(path.read_text(encoding='utf-8'))

def capture(path,expected=None):
 command=['python3',CAPTURE,'--part-type','hbm','--display-name','HBM','--samples','10',
          '--timeout-sec','25','--max-position-span-mm','1.1','--max-angle-span-deg','.5',
          '--output',path]
 if expected is None:command+=['--instance-index','1']
 else:
  center=expected['part_center_base_mm']
  command+=['--expected-base-x-mm',str(center[0]),'--expected-base-y-mm',str(center[1]),
            '--max-expected-distance-mm','15']
 run(command,f'CAPTURE {path.stem}');return load(path)

def move(target,height,safe_z,args,label):
 command=[MOVE,'--target-file',target,'--approach-offset-mm',str(height),
  '--align-part','--gripper-axis','tool_y','--center-correction',
  '--tool-correction-x-mm',str(args.tool_correction_x_mm),
  '--tool-correction-y-mm',str(args.tool_correction_y_mm),
  '--speed-percent','30','--descent-speed-percent','10','--rotation-speed-percent','20',
  '--safe-z-mm',str(safe_z),'--safe-clearance-mm','100','--max-distance-mm','450',
  '--joint-limit-margin-deg','10','--max-joint-step-deg','90',
  '--workspace-x-min','-700','--workspace-x-max','-150',
  '--workspace-y-min','-350','--workspace-y-max','350',
  '--workspace-z-min','-60','--workspace-z-max','650']
 command+=['--execute','--confirm-move'] if args.execute else ['--dry-run']
 run(command,label)

def delta(first,second):
 a=np.asarray(first['part_center_base_mm'],float);b=np.asarray(second['part_center_base_mm'],float)
 da=((float(second['long_axis_angle_base_deg'])-float(first['long_axis_angle_base_deg'])+90)%180)-90
 return b-a,da

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--execute',action='store_true');p.add_argument('--confirm-coarse-to-fine',action='store_true')
 p.add_argument('--tool-correction-x-mm',type=float,default=-2.05)
 p.add_argument('--tool-correction-y-mm',type=float,default=-2.55)
 p.add_argument('--max-refinement-mm',type=float,default=5.)
 p.add_argument('--max-refinement-angle-deg',type=float,default=2.)
 a=p.parse_args()
 if a.execute!=a.confirm_coarse_to_fine:p.error('actual test requires --execute --confirm-coarse-to-fine')
 coarse_path=DATA/'hbm_c2f_coarse.json';near50_path=DATA/'hbm_c2f_near50.json';near20_path=DATA/'hbm_c2f_near20.json'
 coarse=capture(coarse_path)
 move(coarse_path,50,337.88,a,'MOVE TO 50 MM ABOVE HBM')
 if not a.execute:
  print('DRY RUN stops after validating the first motion plan.');return
 near50=capture(near50_path,coarse);d50,angle50=delta(coarse,near50)
 if np.linalg.norm(d50[:2])>a.max_refinement_mm or abs(angle50)>a.max_refinement_angle_deg:
  raise RuntimeError(f'50 mm refinement too large: dXYZ={d50.tolist()}, dAngle={angle50:.3f}')
 local_safe_z=max(float(coarse['part_center_base_mm'][2])+55.,float(near50['part_center_base_mm'][2])+25.)
 move(near50_path,20,local_safe_z,a,'REFINE AND MOVE TO 20 MM ABOVE HBM')
 near20=capture(near20_path,near50);d20,angle20=delta(near50,near20)
 report={'schema_version':1,'mode':'hbm_coarse_to_fine_noncontact','timestamp_unix':time.time(),
  'tool_correction_mm':[a.tool_correction_x_mm,a.tool_correction_y_mm],
  'coarse':coarse,'near_50mm':near50,'near_20mm':near20,
  'coarse_to_50_delta_base_mm':np.round(d50,4).tolist(),'coarse_to_50_delta_angle_deg':round(angle50,4),
  'near50_to_20_delta_base_mm':np.round(d20,4).tolist(),'near50_to_20_delta_angle_deg':round(angle20,4),
  'golden_grasp_reference_authorized':False,'robot_motion_authorized':False}
 out=DATA/'hbm_coarse_to_fine_report.json';tmp=out.with_suffix('.tmp')
 tmp.write_text(json.dumps(report,indent=2),encoding='utf-8');tmp.replace(out)
 print('\n=== RESULT ===');print(json.dumps({k:report[k] for k in (
  'coarse_to_50_delta_base_mm','coarse_to_50_delta_angle_deg',
  'near50_to_20_delta_base_mm','near50_to_20_delta_angle_deg')},indent=2))
 print(f'Report: {out}');print('Stopped 20 mm above HBM; no grasp or surface descent.')

if __name__=='__main__':main()

"""Read-only freeze of the operator-confirmed remaining 15 tray parts."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
from fixed_cycle_snapshot import atomic_write, validate_tray_detection_quality
from full_cycle_plan import SLOT_PART_SEQUENCE


def bind_leading_empty_grid(kind, detections, consumed_prefix=1):
    """Confirmed set1 leading cell empty; reject ambiguous row/column geometry."""
    sizes={'hbm':[1,2,2,2], 'long_orange':[1,2], 'black_block':[4], 'marked_white':[1]}
    if consumed_prefix not in (1,2) or (consumed_prefix==2 and kind!='hbm'):
        raise RuntimeError('unsupported consumed prefix')
    expected=[2,2,2] if consumed_prefix==2 else sizes[kind]
    rows=[]
    for d in sorted(detections,key=lambda x:x['reference_center_pixel'][1]):
        x,y=map(float,d['reference_center_pixel'])
        if not np.isfinite([x,y]).all():raise RuntimeError('nonfinite grid point')
        if not rows or y-np.mean([p['reference_center_pixel'][1] for p in rows[-1]])>30:rows.append([])
        rows[-1].append(d)
    if [len(r) for r in rows]!=expected:raise RuntimeError(f'{kind} remaining row pattern mismatch')
    for row in rows:
        row.sort(key=lambda x:x['reference_center_pixel'][0])
        if np.ptp([d['reference_center_pixel'][1] for d in row])>15:raise RuntimeError('row not level')
        if len(row)>1 and min(np.diff([d['reference_center_pixel'][0] for d in row]))<30:raise RuntimeError('columns ambiguous')
    if kind in ('hbm','long_orange'):
        paired=rows if consumed_prefix==2 else rows[1:]
        left=np.median([r[0]['reference_center_pixel'][0] for r in paired])
        right=np.median([r[1]['reference_center_pixel'][0] for r in paired])
        if consumed_prefix==1 and abs(rows[0][0]['reference_center_pixel'][0]-right)>15:raise RuntimeError('first-row survivor is not right cell')
        for row in paired:
            if max(abs(row[0]['reference_center_pixel'][0]-left),abs(row[1]['reference_center_pixel'][0]-right))>15:raise RuntimeError('column alignment failed')
    return [(d,i) for i,d in enumerate([d for row in rows for d in row],consumed_prefix+1)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--confirmed-leading-empty-grid',action='store_true')
    p.add_argument('--exclude-released-hbm02',action='store_true')
    a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    live=json.loads((root/'data/tray_detections_last.json').read_text())
    reference=json.loads(a.reference.read_text())
    recipes=json.loads((root/'config/part_gripper_recipes.json').read_text())
    age=time.time()-live['timestamp_ros_ns']/1e9
    if not 0<=age<10 or live['tray_registration']!='TRACKING' or live['base_transform_status'] not in ('OK','VALID_COORDINATES_ONLY'):
        raise RuntimeError('fresh registered tray required')
    selected=[(s,t) for s,t in SLOT_PART_SEQUENCE if not s.startswith(('GPU-','CAP-')) and not s.endswith('-01')]
    if a.exclude_released_hbm02:
        selected=[(s,t) for s,t in selected if s!='HBM-02']
    parts=[];bindings=[]
    for kind in sorted({t for s,t in selected}):
        indices=[int(s.split('-')[1]) for s,t in selected if t==kind]
        refs=[r for r in reference['tray_capture']['parts'] if r['part_type']==kind and r['instance_index'] in indices]
        detections=[r for r in live['stable_detections'] if r['part_type']==kind]
        if len(refs)!=len(indices) or len(detections)!=len(indices): raise RuntimeError(f'{kind} count mismatch')
        if a.confirmed_leading_empty_grid:
            prefix=2 if kind=='hbm' and a.exclude_released_hbm02 else 1
            for d,index in bind_leading_empty_grid(kind,detections,prefix):
                q=validate_tray_detection_quality(d,recipes['tray_snapshot_quality'])
                parts.append(dict(part_type=kind,instance_index=index,consumed=False,
                                  base_xyz_mm=d['base_xyz_mm'],long_axis_angle_base_deg=d['long_axis_angle_base_deg'],
                                  observation_frames=d['observation_frames'],quality=q))
                bindings.append(dict(part_type=kind,detector_index=d['instance_index'],physical_index=index,
                                     reference_center_pixel=d['reference_center_pixel'],method='operator_confirmed_leading_empty_grid'))
            continue
        distances=np.array([[np.linalg.norm(np.array(d['base_xyz_mm'][:2])-np.array(r['base_xyz_mm'][:2])) for r in refs] for d in detections])
        ii,jj=linear_sum_assignment(distances)
        for i,j in zip(ii,jj):
            if distances[i,j]>5: raise RuntimeError(f'{kind}: reference cell moved more than 5mm: {distances[i,j]:.3f}')
            others=np.delete(distances[i],j)
            if len(others) and others.min()-distances[i,j]<2: raise RuntimeError('ambiguous physical cell identity')
            d=detections[i];r=refs[j]
            q=validate_tray_detection_quality(d,recipes['tray_snapshot_quality'])
            parts.append(dict(part_type=kind,instance_index=r['instance_index'],consumed=False,
                              base_xyz_mm=d['base_xyz_mm'],long_axis_angle_base_deg=d['long_axis_angle_base_deg'],
                              observation_frames=d['observation_frames'],quality=q))
            bindings.append(dict(part_type=kind,detector_index=d['instance_index'],physical_index=r['instance_index'],distance_mm=float(distances[i,j])))
    output=dict(schema='fr5.remaining_non_smd_tray/v1',timestamp_unix=live['timestamp_ros_ns']/1e9,
                authorized_selected_slots=[s for s,t in selected],parts=parts,bindings=bindings,
                handeye_sha256=live['handeye_sha256'],robot_motion_authorized=False)
    if a.output.exists(): raise RuntimeError('refusing to overwrite capture')
    atomic_write(a.output,output)
    print(json.dumps({'count':len(parts),'bindings':bindings},indent=2))


if __name__=='__main__':main()

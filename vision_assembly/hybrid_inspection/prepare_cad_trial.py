"""Create isolated CAD-boundary crop config; never replaces live config."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment
from extract_unity_socket_candidates import extract
from preprocessor_and_cropper import FixedSlotCropper

ROOT=Path(__file__).resolve().parents[2]


def main():
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    layout=copy.deepcopy(cropper.layout)
    spec=json.loads((ROOT/'vision_assembly/config/unity_socket_clearance.json').read_text())
    mesh=Path('/home/hc/My project/Assets/반도체 기판 모델링(Unity)/ASt/motherBoard.obj')
    faces=extract(mesh,spec)
    scale=layout['board']['unity_to_physical_scale']
    mapping=[]
    for kind in spec['component_types']:
        slots=[p for p in layout['placements'] if p['component_type']==kind]
        group=[f for f in faces if f['component_type']==kind]
        if len(slots)!=len(group):
            raise ValueError(f'Count mismatch: {kind}')
        polygons=[-np.array(f['polygon_obj_xz_mm'])*[scale['x'],scale['y']] for f in group]
        centers=[(p.min(axis=0)+p.max(axis=0))/2 for p in polygons]
        cost=np.array([[np.linalg.norm(np.array([s['center_board_mm']['x'],s['center_board_mm']['y']])-c)
                        for c in centers] for s in slots])
        ri,ci=linear_sum_assignment(cost)
        for i,j in zip(ri,ci):
            if cost[i,j]>3.0:
                raise ValueError(f'Unresolved slot mapping: {slots[i]["slot_id"]} {cost[i,j]}mm')
            s=slots[i]; p=polygons[j]; size=np.ptp(p,axis=0)
            s['center_board_mm']=dict(x=float(centers[j][0]),y=float(centers[j][1]))
            s['nominal_size_mm'].update(x=float(size[0]),y=float(size[1]))
            s['coordinate_status']='UNVALIDATED_CAD_SOCKET_BOUNDING_CROP_TRIAL'
            mapping.append(dict(slot_id=s['slot_id'],face_index=group[j]['face_index'],
                                mapping_distance_mm=float(cost[i,j]),polygon_board_mm=p.tolist()))
    out=Path(tempfile.mkdtemp(prefix='cad_yellow_trial_',dir=ROOT/'runtime/inspection'))
    config=copy.deepcopy(cropper.config)
    physical=json.loads((ROOT/config['physical_board']).read_text())
    physical['component_slot_overrides']={}
    config['board_layout']=str(out/'layout.json')
    config['physical_board']=str(out/'physical.json')
    # Corrections calibrated for old reference centers must not move CAD centers.
    config['auxiliary_pose_slot_reference_offsets_mm']={}
    config['auxiliary_pose_use_active_slot_centers']=True
    config['provider_crop_config']=str(ROOT/'vision_assembly/config/full_board_inspection.json')
    for name,data in [('layout.json',layout),('physical.json',physical),('config.json',config),
                      ('trial.json',dict(status='ADVISORY_EXPERIMENT_ONLY',mapping=mapping,
                       mesh_sha256=hashlib.sha256(mesh.read_bytes()).hexdigest(),
                       limitation='Crops use bounding rectangles of yellow floor polygons. IND six-sided polygon is preserved here but crop itself is rectangular. Existing learned weights are not recalibrated for changed crops. No live config or release authority changes.'))]:
        (out/name).write_text(json.dumps(data,indent=2))
    print(out)


if __name__=='__main__':
    main()

"""Offline integer x-only legacy-pin replay. No runtime imports or pose votes."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from audit_hbm_column_displacement import displacement
from hbm_individual_pins import compare


def replay(reference, sample):
    baseline = compare(reference, sample)
    rgb = [cv2.cvtColor(im, cv2.COLOR_BGR2RGB) for im in (reference,sample)]
    sides = displacement(*rgb)
    shifts = [s['dx_px'] for s in sides.values()]
    if any(s is None for s in shifts) or abs(shifts[0]-shifts[1])>2 or max(map(abs,shifts))>12:
        return {'status':'UNKNOWN','applied':False,'baseline':baseline,'candidate':baseline}
    dx = int(round(float(np.mean(shifts))))
    # Integer-only diagnostic copy; reference y anchors and endpoint coverage
    # are retained. Original image, slot pose and direction remain untouched.
    aligned = np.zeros_like(sample)
    if dx>0:
        aligned[:,:-dx]=sample[:,dx:]
    elif dx<0:
        aligned[:,-dx:]=sample[:,:dx]
    else:
        aligned[:]=sample
    candidate = compare(reference,aligned)
    for side in candidate:
        for point in side['defect_points_px']:
            point[0] += dx
    return {'status':'UNKNOWN','applied':True,'dx_px':dx,'baseline':baseline,'candidate':candidate}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    manifest=json.loads((root/'vision_assembly/config/hbm_pin_reference.json').read_text())
    rows=[]
    for run in args.run:
        for slot,entry in manifest['slots'].items():
            ref=root/entry['path']
            path=run/'fixed_slots/hbm'/f'{slot}.png'
            if hashlib.sha256(ref.read_bytes()).hexdigest()!=entry['sha256']:
                raise ValueError('Reference mismatch')
            images=[cv2.imread(str(p)) for p in (ref,path)]
            if any(im is None for im in images):
                raise ValueError('Unreadable crop')
            result=replay(*images)
            rows.append({'run':str(run),'slot_id':slot,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),**result})
            print(run.name,slot,result['applied'],
                  [(s['status'],s['missing_indices']) for s in result['baseline']], '=>',
                  [(s['status'],s['missing_indices']) for s in result['candidate']])
    with args.output.open('x') as stream:
        json.dump({'authority':'OFFLINE_ONLY','status':'UNKNOWN','rows':rows},stream,indent=2)


if __name__=='__main__':
    main()

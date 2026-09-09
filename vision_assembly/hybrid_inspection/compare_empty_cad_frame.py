"""Compare fixed CAD against empty and occupied boards without local fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from preprocessor_and_cropper import FixedSlotCropper


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--empty',type=Path,required=True)
    parser.add_argument('--occupied',type=Path,required=True)
    parser.add_argument('--trial',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    trial=json.loads((args.trial/'config.json').read_text())
    cropper=FixedSlotCropper(Path(trial['provider_crop_config']))
    mapping=json.loads((args.trial/'trial.json').read_text())['mapping']
    boards=[]; metadata=[]
    for path in (args.empty,args.occupied):
        source=cv2.imread(str(path))
        if source is None: raise ValueError('Missing source image')
        registered=cropper.register(source)
        if registered.alignment_reason!='OK' or registered.alignment_score<cropper.config['global_alignment']['minimum_score']:
            raise ValueError('Invalid board registration')
        boards.append(registered.image_bgr.copy())
        metadata.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             alignment_score=registered.alignment_score))
    args.output.mkdir(parents=True,exist_ok=False)
    for slot in mapping:
        polygon=np.array(slot['polygon_board_mm'])
        px=(.5-polygon/np.array(cropper.board_size_mm))*[1600,1266]
        lo=np.maximum(np.floor(px.min(axis=0)-20).astype(int),[0,0])
        hi=np.minimum(np.ceil(px.max(axis=0)+20).astype(int),[1600,1266])
        panels=[]
        for board in boards:
            # Retain an unannotated view so the line does not hide the actual wall.
            plain=board[lo[1]:hi[1],lo[0]:hi[0]].copy()
            annotated=plain.copy()
            cv2.polylines(annotated,[np.rint(px-lo).astype(np.int32)],True,(0,220,255),1)
            panels.extend([plain,annotated])
        if not cv2.imwrite(str(args.output/(slot['slot_id']+'.png')),np.hstack(panels)):
            raise OSError('Could not write comparison')
    (args.output/'provenance.json').write_text(json.dumps(dict(sources=metadata,
        columns=['empty_original','empty_CAD','occupied_original','occupied_CAD'],
        trial_sha256=hashlib.sha256((args.trial/'trial.json').read_bytes()).hexdigest(),
        authority='ADVISORY_ONLY',local_registration=False,runtime_changed=False,
        note='Historical empty board, not a new empty capture. CAD line is not verified wall. Native pixels; board-level registration only.'),indent=2))
    print(json.dumps(metadata))


if __name__=='__main__': main()

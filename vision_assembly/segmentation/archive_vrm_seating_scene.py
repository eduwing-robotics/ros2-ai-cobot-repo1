"""Archive a user-labelled single VRM scene; do not infer other slot labels."""
import argparse
import hashlib
import json
import cv2
from build_vrm_fixed_crop_dataset import ROOT, FixedSlotCropper


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--label',required=True,choices=['FLAT','SEATING'])
    parser.add_argument('--basis',required=True)
    parser.add_argument('--split',choices=['development_pending_review','validation'],default='development_pending_review')
    args=parser.parse_args()
    source=(ROOT/args.image).resolve()
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    board=cropper.register(cv2.imread(str(source)))
    if board.alignment_reason!='OK' or board.alignment_score<float(cropper.config['global_alignment']['minimum_score']):
        raise ValueError('Uncertain registration; cannot archive matched crop')
    slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_05')
    cx,cy,w,h=slot.geometry
    cw,ch=round(w*1.5),round(h*1.5)
    x,y=round(cx-cw/2),round(cy-ch/2)
    crop=board.image_bgr[y:y+ch,x:x+cw]
    if x<0 or y<0 or crop.shape[:2]!=(ch,cw):
        raise ValueError('Invalid crop')
    output=ROOT/'runtime/inspection/vrm_seating_pairs'/source.stem
    output.mkdir(parents=True,exist_ok=False)
    target=output/'vrm_05.png'
    if not cv2.imwrite(str(target),crop):
        raise IOError('Crop write failed')
    record=dict(physical_scene_id=source.stem,target_slot='vrm_05',
        seating_label=args.label,label_basis=args.basis,
        image=str(source),image_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        crop=str(target),crop_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        crop_origin_px=[x,y],crop_size_px=[cw,ch],alignment_score=board.alignment_score,
        planned_split=args.split,training_allowed=False,training_ingested=False,
        whole_board_normal=False,other_slots_labelled=False,
        flash='off',robot_command_sent=False,conveyor_command_sent=False)
    (output/'scene.json').write_text(json.dumps(record,indent=2))
    print(output)
    print('alignment',board.alignment_score)


if __name__=='__main__':
    main()

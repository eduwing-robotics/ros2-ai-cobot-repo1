"""Real-crop bridge replay and isolated provider/display checks, no deployment."""
import json
import argparse
import sys
from dataclasses import asdict
import torch
import cv2
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper

sys.path.insert(0,str(ROOT/'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import VrmSeatingClassifier, VrmStateClassifier
from main import fuse_required_stages, build_advisory_candidates, _vrm_non_empty_confidence


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--actual-presence',action='store_true')
    args=parser.parse_args()
    torch.set_num_threads(2)
    root=ROOT/'runtime/inspection/vrm_multiscale_seating_plus_165057/integration_bridge'
    metadata=json.loads((root/'vrm_seating.json').read_text())
    assert metadata['runtime_enabled'] is False
    provider=VrmSeatingClassifier(root,device='cpu')
    # Isolated in-memory harness only. No metadata file or active provider is changed.
    provider.model=torch.jit.load(str(root/'vrm_seating.torchscript.pt')).eval()
    provider.model_path=root/'vrm_seating.torchscript.pt'
    provider.metadata={**metadata,'runtime_enabled':True,'seating_min_probability':.5}
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    state_provider=VrmStateClassifier(ROOT/'vision_assembly/slot_classifier/models',device='cpu')
    rows=[]
    for stamp,kind in [('165413','normal'),('165642','translation'),('165914','translation'),('170142','normal')]:
        source=json.loads((ROOT/f'runtime/inspection/vrm_multiscale_{kind}_holdout_{stamp}.json').read_text())
        assert source['candidates'][0]['sha256']==metadata['source_sha256']
        expected={r['slot']:r['seating_score'] for r in source['candidates'][0]['rows']}
        board=cropper.register(cv2.imread(str(ROOT/source['image'])))
        assert board.alignment_reason=='OK' and board.alignment_score>=float(cropper.config['global_alignment']['minimum_score'])
        for slot in cropper.fixed_slots(board.image_bgr):
            if slot.component_type!='VRM':
                continue
            result=provider.inspect(slot,board.image_bgr,non_empty_confidence=.99)
            error=abs(result.probabilities['SEATING']-expected[slot.slot_id])
            assert error<1e-5, error
            blocked=provider.inspect(slot,board.image_bgr,non_empty_confidence=.1)
            assert blocked.status=='UNKNOWN' and blocked.predicted_state=='UNKNOWN'
            stages={k:{'status':'UNKNOWN','authority':'ADVISORY_ONLY'} for k in ('presence','pose','orientation','surface')}
            stages['seating']=asdict(result)
            assert fuse_required_stages(stages)[0]=='UNKNOWN'
            candidates=build_advisory_candidates([dict(slot_id=slot.slot_id,component_type='VRM',stages=stages)])
            shown=any('SEATING?' in c['codes'] for c in candidates)
            assert shown==(expected[slot.slot_id]>=.5)
            actual={}
            if args.actual_presence:
                state=state_provider.inspect(slot,board.image_bgr)
                nonempty=_vrm_non_empty_confidence(state)
                actual_result=provider.inspect(slot,board.image_bgr,non_empty_confidence=nonempty)
                actual=dict(state=asdict(state),non_empty_confidence=nonempty,
                    actual_seating=asdict(actual_result),gate_passed=bool(actual_result.probabilities))
            rows.append(dict(stamp=stamp,slot=slot.slot_id,absolute_score_error=error,
                advisory_display=shown,status='UNKNOWN',nonempty_gate_test='PASS',**actual))
    empty_rows=[]
    if args.actual_presence:
        board=cropper.register(cv2.imread(str(ROOT/'runtime/inspection/s22_inspection_roi_20260905_134637.png')))
        assert board.alignment_reason=='OK' and board.alignment_score>=float(cropper.config['global_alignment']['minimum_score'])
        for slot in cropper.fixed_slots(board.image_bgr):
            if slot.component_type!='VRM':
                continue
            state=state_provider.inspect(slot,board.image_bgr)
            nonempty=_vrm_non_empty_confidence(state)
            result=provider.inspect(slot,board.image_bgr,non_empty_confidence=nonempty)
            empty_rows.append(dict(slot=slot.slot_id,state=asdict(state),
                non_empty_confidence=nonempty,seating=asdict(result),gate_passed=bool(result.probabilities)))
    assert json.loads((root/'vrm_seating.json').read_text())['runtime_enabled'] is False
    report=dict(runtime_changed=False,authority='ADVISORY_ONLY',rows=rows,
        limitation='Offline provider-chain test, no full-board end-to-end run. Presence is actual model output only when actual_presence=true.',
        actual_presence=args.actual_presence,empty_rows=empty_rows,
        maximum_score_error=max(r['absolute_score_error'] for r in rows),
        robot_command_sent=False,conveyor_command_sent=False)
    (root/('actual_presence_integration_test.json' if args.actual_presence else 'real_crop_integration_test.json')).write_text(json.dumps(report,indent=2))
    print('checked',len(rows),'crops; max error',report['maximum_score_error'])
    if args.actual_presence:
        print('present gate passed',sum(r['gate_passed'] for r in rows),'/',len(rows))
        print('empty gate passed',sum(r['gate_passed'] for r in empty_rows),'/',len(empty_rows))


if __name__=='__main__':
    main()

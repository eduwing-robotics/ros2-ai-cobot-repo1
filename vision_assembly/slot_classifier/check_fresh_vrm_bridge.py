"""Exercise the production provider in memory, without activating the candidate."""
import json
import sys
from dataclasses import asdict
from pathlib import Path
import cv2
import torch
from evaluate_vrm_texture_presence import ROOT, FixedSlotCropper

sys.path.insert(0, str(ROOT/'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import VrmSeatingClassifier, VrmStateClassifier
from main import build_advisory_candidates, fuse_required_stages, _vrm_non_empty_confidence


def main():
    torch.set_num_threads(2)
    source=ROOT/'runtime/inspection/vrm_seating_fresh_vrm5_20260907'
    bridge=source/'integration_bridge'
    metadata=json.loads((bridge/'vrm_seating.json').read_text())
    assert metadata['runtime_enabled'] is False
    provider=VrmSeatingClassifier(bridge,device='cpu')
    provider.model=torch.jit.load(str(bridge/'vrm_seating.torchscript.pt')).eval()
    provider.model_path=bridge/'vrm_seating.torchscript.pt'
    provider.metadata={**metadata,'runtime_enabled':True,'seating_min_probability':.5}
    state=VrmStateClassifier(ROOT/'vision_assembly/slot_classifier/models',device='cpu')
    cropper=FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    evaluation=json.loads((source/'evaluation.json').read_text())['rows']
    records=json.loads((source/'fresh_manifest.json').read_text())
    results=[]
    for record in records:
        board=cropper.register(cv2.imread(str(ROOT/record['scene_id'])))
        assert board.alignment_reason=='OK'
        assert board.alignment_score>=float(cropper.config['global_alignment']['minimum_score'])
        slot=next(s for s in cropper.fixed_slots(board.image_bgr) if s.slot_id=='vrm_05')
        expected=next(r['seating_score'] for r in evaluation if r['source']==record['scene_id'] and r['slot']=='vrm_05')
        raw=provider.inspect(slot,board.image_bgr,non_empty_confidence=.99)
        error=abs(raw.probabilities['SEATING']-expected)
        assert error<1e-5
        blocked=provider.inspect(slot,board.image_bgr,non_empty_confidence=.1)
        assert blocked.status=='UNKNOWN' and not blocked.probabilities
        presence=state.inspect(slot,board.image_bgr)
        result=provider.inspect(slot,board.image_bgr,non_empty_confidence=_vrm_non_empty_confidence(presence))
        stages={name:{'status':'UNKNOWN','authority':'ADVISORY_ONLY'} for name in ('pose','orientation','surface')}
        stages.update(presence=asdict(presence),seating=asdict(result))
        assert fuse_required_stages(stages)[0]=='UNKNOWN'
        candidates=build_advisory_candidates([dict(slot_id='vrm_05',component_type='VRM',stages=stages)])
        results.append(dict(image=record['scene_id'],split=record['split'],label=record['label'],
            score=expected,error=error,presence=asdict(presence),seating=asdict(result),candidates=candidates))
    (bridge/'fresh_provider_check.json').write_text(json.dumps(dict(runtime_changed=False,
        rows=results,max_error=max(r['error'] for r in results),
        limitation='In-memory provider/display test only; not production promotion or full-board validation',
        robot_command_sent=False,conveyor_command_sent=False),indent=2))
    print('checked',len(results),'max error',max(r['error'] for r in results))
    for r in results:
        if r['split']=='fresh_validation':
            print(r['image'],r['label'],round(r['score'],6),r['seating']['reason'],[c['codes'] for c in r['candidates']])


if __name__=='__main__':
    main()

"""Compare frozen candidate and previous checkpoint on identical fresh crops."""
import json
import argparse
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'vision_assembly/inspection'))
from predict_component_patchcore import _checkpoint, _predict_outputs


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--restored-pair',action='store_true')
    parser.add_argument('--restored-repeat',action='store_true')
    parser.add_argument('--confirmed-i1',action='store_true')
    args=parser.parse_args()
    if args.restored_repeat:
        args.restored_pair=True
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    folder=ROOT/'runtime/inspection'/('inductor_restored_pair_live_20260906' if args.restored_pair else 'inductor_current_normal_live_20260906')
    if args.restored_repeat:
        folder=ROOT/'runtime/inspection/inductor_restored_repeat_live_20260906'
    if args.confirmed_i1:
        folder=ROOT/'runtime/inspection/inductor_confirmed_i1_live_20260906'
    reports=sorted(folder.glob('*/hybrid_report.json'))
    if len(reports)!=3:
        raise RuntimeError('Expected exactly three fresh trials')
    crops=folder/'same_image_comparison/crops'
    crops.mkdir(parents=True,exist_ok=True)
    rows=[]
    hashes=set()
    for p in reports:
        report=json.loads(p.read_text())
        hashes.add(report['input_sha256'])
        ids={s['slot_id']:s for s in report['slots']}
        candidates={s['slot_id']:s['codes'] for s in report['advisory_candidates']['items']}
        if args.confirmed_i1 and 'smd_capacitor_01' in candidates:
            raise RuntimeError('Confirmed normal SMD1 still flagged')
        for idx in [1,2]:
            slot=f'inductor_0{idx}'
            name=f'{p.parent.name}_{slot}.png'
            shutil.copy2(p.parent/'patchcore_crops/inductor'/f'{slot}.png',crops/name)
            rows.append(dict(name=name,slot=slot,report=str(p),candidate_score=ids[slot]['stages']['surface']['score'],
                             codes=candidates.get(slot,[]),robot_command_sent=report['robot_command_sent'],
                             conveyor_command_sent=report['conveyor_command_sent']))
        if report['status']!='UNKNOWN':
            raise RuntimeError('Unverified fusion authority changed')
    if len(hashes)!=3:
        raise RuntimeError('Repeated image hash')
    previous_root=ROOT/'runtime/inspection/patchcore'/('inductor_current_normal_candidate_20260906/models' if args.restored_pair else 'pcb_components_strict_v4')
    if args.confirmed_i1:
        previous_root=ROOT/'runtime/inspection/patchcore/inductor_restored_repeat_candidate_20260906/models'
    old=_predict_outputs('inductor',crops,_checkpoint(previous_root,'inductor'),folder/'same_image_comparison/previous')
    for row in rows:
        row['previous_score']=float(old[Path(row['name']).stem]['score'])
    valid=all(not r['codes'] if args.restored_pair or r['slot']=='inductor_01' else 'DIR?' in r['codes'] for r in rows)
    valid=valid and not any(r['robot_command_sent'] or r['conveyor_command_sent'] for r in rows)
    payload=dict(rows=rows,three_fresh_trials_passed=valid,authority='ADVISORY_ONLY',previous_model_root=str(previous_root),
        expected={'inductor_01':'normal','inductor_02':'normal' if args.restored_pair else 'direction_defect'},
        limitation='Same physical parts and current placement; not long-term lighting or microcrack qualification. User observations assumed unchanged. No autonomous PASS authority.')
    (folder/'validation.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps(payload,indent=2))
    if not valid:
        raise RuntimeError('Candidate fresh trial failure; do not promote')


if __name__=='__main__':
    main()

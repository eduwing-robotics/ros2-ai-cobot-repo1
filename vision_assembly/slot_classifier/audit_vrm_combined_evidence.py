"""Offline OR/AND comparison. No advisory evidence can grant PASS/FAIL."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def combine(score, excess):
    if score is None or excess is None:
        return dict(status='UNKNOWN', any_warning=None, both_warning=None, reason='MISSING_EVIDENCE')
    model_warning = score >= .5
    edge_warning = excess > 0
    return dict(status='UNKNOWN', model_warning=model_warning, edge_warning=edge_warning,
                any_warning=model_warning or edge_warning, both_warning=model_warning and edge_warning)


def main():
    candidate=ROOT/'runtime/inspection/vrm_spatial4_seating_four_scenes_154302'
    digest=hashlib.sha256((candidate/'candidate.npz').read_bytes()).hexdigest()
    scores={}
    for r in json.loads((candidate/'evaluation.json').read_text())['rows']:
        if r['split']=='session_holdout':
            stamp=Path(r['source']).stem.rsplit('_',1)[-1]
            scores[stamp,r['slot']]=r['seating_score']
    for stamp,kind in [('154927','normal'),('155509','translation'),('155745','translation'),('160027','translation')]:
        report=json.loads((ROOT/f'runtime/inspection/vrm_spatial_{kind}_holdout_{stamp}.json').read_text())
        c=next(c for c in report['candidates'] if c['sha256']==digest)
        for r in c['rows']:
            scores[stamp,r['slot']]=r['seating_score']
    edges=json.loads((ROOT/'runtime/inspection/vrm_edge_profiles_regression_160027/slot_envelopes.json').read_text())['rows']
    rows=[]
    for edge in edges:
        score=scores.get((edge['stamp'],edge['slot']))
        rows.append(dict(stamp=edge['stamp'],slot=edge['slot'],expected=edge['expected'],
            score=score,edge_excess_px=edge['paired_excess_px'],**combine(score,edge['paired_excess_px'])))
    summary={}
    for key in ('model_warning','edge_warning','any_warning','both_warning'):
        available=[r for r in rows if r.get(key) is not None]
        summary[key]=dict(normal_count=sum(r['expected']=='PASS' for r in available),
            normal_warnings=sum(r['expected']=='PASS' and r[key] for r in available),
            defect_count=sum(r['expected']=='FAIL' for r in available),
            defect_warnings=sum(r['expected']=='FAIL' and r[key] for r in available))
    out=ROOT/'runtime/inspection/vrm_combined_evidence_audit_160027.json'
    out.write_text(json.dumps(dict(authority='ADVISORY_ONLY',runtime_enabled=False,
        note='Retrospective development comparison; edge excess>0 is descriptive, not a calibrated tolerance. No trained provider or runtime thresholds changed.',
        model_sha256=digest,summary=summary,rows=rows,robot_command_sent=False,conveyor_command_sent=False),indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()

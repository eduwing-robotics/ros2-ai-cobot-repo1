"""Joint edge selection experiment; bounded hypotheses, no production verdict."""
import itertools
import json
import hashlib
import numpy as np
from probe_vrm_robust_edges import fit_candidates, ROOT
from vrm_line_pose_evidence import polygon_from_edges


def joint_rectangle(options):
    if len(options)!=4 or any(not o for o in options):
        return dict(status='UNKNOWN',measurement_available=False,reason='MISSING_EDGE')
    candidates=[]
    normalizers=[max(h['strength'] for h in o) for o in options]
    for combination in itertools.product(*options):
        shape=polygon_from_edges([dict(candidate=h,ambiguous=False) for h in combination])
        if shape is None:
            continue
        score=sum(h['support']+h['strength']/max(scale,1e-9) for h,scale in zip(combination,normalizers))
        candidates.append(dict(**shape,score=score))
    if not candidates:
        return dict(status='UNKNOWN',measurement_available=False,reason='NO_COHERENT_RECTANGLE')
    candidates.sort(key=lambda r:r['score'],reverse=True)
    best=candidates[0]
    competitors=[r for r in candidates[1:] if np.max(np.linalg.norm(
        np.array(r['corners_px'])-best['corners_px'],axis=1))>4]
    rival=competitors[0] if competitors else None
    ambiguous=bool(rival and best['score']-rival['score']<2)
    return dict(status='UNKNOWN',measurement_available=not ambiguous,
                reason='COMPETING_RECTANGLES' if ambiguous else 'UNVERIFIED_RECTANGLE',
                candidate=best,competitor=rival,coherent_count=len(candidates))


def evaluate(raw,clahe):
    def options(edges):
        return [fit_candidates(e['samples']).get('alternatives',[]) for e in edges]
    a,b=joint_rectangle(options(raw)),joint_rectangle(options(clahe))
    result=dict(status='UNKNOWN',authority='ADVISORY_ONLY',measurement_available=False,raw=a,clahe=b)
    if not a['measurement_available'] or not b['measurement_available']:
        return dict(**result,reason='AMBIGUOUS_OR_MISSING_RECTANGLE')
    gap=float(np.max(np.linalg.norm(np.array(a['candidate']['corners_px'])-
                                   b['candidate']['corners_px'],axis=1)))
    if gap>4:
        return dict(**result,reason='RAW_CLAHE_CORNER_DISAGREEMENT',corner_gap_px=gap)
    result['measurement_available']=True
    return dict(**result,reason='UNVERIFIED_POSE',corner_gap_px=gap,
                center_px=a['candidate']['center_px'],angle_deg=a['candidate']['angle_deg'])


def main():
    rows=[]
    for name in ('vrm_robust_edges_pose_regression','vrm_robust_edges_190202'):
        source=ROOT/'runtime/inspection'/name/'report.json'
        for r in json.loads(source.read_text())['rows']:
            image=ROOT/f'runtime/inspection/s22_inspection_roi_20260905_{r["stamp"]}.png'
            if hashlib.sha256(image.read_bytes()).hexdigest()!=r['image_sha256']:
                raise ValueError('Image no longer matches stored edges')
            rows.append(dict(stamp=r['stamp'],slot=r['slot'],image_sha256=r['image_sha256'],
                             **evaluate(r['raw'],r['clahe'])))
    result=dict(rows=rows,authority='ADVISORY_ONLY',runtime_enabled=False,
        robot_command_sent=False,conveyor_command_sent=False,
        limitations='At most4 hypotheses per edge. No physical tolerances or learned-provider input changes. Availability does not establish correct part boundary or presence; unseen alternatives can remain.')
    output=ROOT/'runtime/inspection/vrm_joint_rectangle_20260905.json'
    output.write_text(json.dumps(result,indent=2))
    print('available',sum(r['measurement_available'] for r in rows),'/',len(rows))
    for r in rows:
        print(r['stamp'],r['slot'],r['reason'],r.get('angle_deg'))


if __name__=='__main__':
    main()

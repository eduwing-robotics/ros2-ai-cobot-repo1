"""Compare two frozen providers without inventing presence or clearance verdicts."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def compare(left,right):
    if (left['scene'],left['slot'],left['image_sha256']) != (right['scene'],right['slot'],right['image_sha256']):
        raise ValueError('Providers do not refer to the same slot and image')
    result=dict(status='UNKNOWN',authority='ADVISORY_ONLY',confirmed_defect=False,
                presence_verdict='UNKNOWN',geometry_validated=False)
    counts=[r.get('unique_central_count',r['central_candidate_count']) for r in (left,right)]
    if any(count>1 for count in counts):
        return dict(result,reason='AMBIGUOUS_BOUNDARY')
    if any(count==0 or r.get('primary') is None for count,r in zip(counts,(left,right))):
        return dict(result,reason='BOUNDARY_UNAVAILABLE_NOT_ABSENCE')
    polygons=[]
    for row in (left,right):
        polygon=np.asarray(row['primary']['polygon'],dtype=float)
        origin=np.asarray(row['crop_origin_px'],dtype=float)
        if polygon.ndim!=2 or polygon.shape[1]!=2 or len(polygon)<3 or not np.isfinite(polygon).all() or not np.isfinite(origin).all():
            raise ValueError('Invalid geometry')
        polygons.append(polygon+origin)
    bounds=[np.r_[p.min(axis=0),p.max(axis=0)] for p in polygons]
    differences=np.abs(bounds[0]-bounds[1])
    return dict(result,reason='TWO_BOUNDARIES_UNCALIBRATED',
        provider_extents_board_px=[p.tolist() for p in bounds],
        edge_difference_px=differences.tolist(),max_edge_difference_px=float(differences.max()),
        note='Agreement does not prove correct contour or seating. No threshold or averaged replacement boundary.')


def main():
    runs=ROOT/'vision_assembly/segmentation/runs'
    paths=[runs/'vrm_fixed_boundary_negative_v1/saved_scene_validation_last/report.json',
           runs/'vrm_boundary_640_candidate_20260907/saved_scene_validation/report.json']
    reports=[json.loads(p.read_text()) for p in paths]
    tables=[{(r['scene'],r['slot']):r for r in d['rows']} for d in reports]
    if tables[0].keys()!=tables[1].keys():
        raise ValueError('Different evaluation scopes')
    rows=[]
    for key,left in tables[0].items():
        right=tables[1][key]
        source=Path(left['source_image'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=left['image_sha256']:
            raise ValueError('Changed source image')
        rows.append(dict(scene=key[0],slot=key[1],expected_presence=left['expected_presence'],
            comparison=compare(left,right)))
    reasons={reason:sum(r['comparison']['reason']==reason for r in rows)
        for reason in {r['comparison']['reason'] for r in rows}}
    deltas=[r['comparison']['max_edge_difference_px'] for r in rows if 'max_edge_difference_px' in r['comparison']]
    output=ROOT/'runtime/inspection/vrm_dual_provider_comparison.json'
    data=dict(rows=rows,summary=reasons,
        difference_percentiles_px=np.percentile(deltas,[0,50,90,100]).tolist() if deltas else [],
        provider_hashes=[d['weights_sha256'] for d in reports],
        authority='ADVISORY_ONLY',runtime_changed=False,
        limitation='Retrospective model comparison, no contour ground truth, no metric tolerance selected.',
        robot_command_sent=False,conveyor_command_sent=False)
    output.write_text(json.dumps(data,indent=2))
    print(reasons)
    print('min/median/p90/max edge difference px',data['difference_percentiles_px'])


if __name__=='__main__':
    main()

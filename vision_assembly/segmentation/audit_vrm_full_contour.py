"""Compare full fixed-frame VRM5 masks to normals without pose alignment."""
import hashlib
import json
from pathlib import Path
import numpy as np
from audit_vrm_label_boundary_error import errors

ROOT = Path(__file__).resolve().parents[2]


def main():
    base = ROOT/'runtime/inspection/vrm_seating_pairs'
    selection = json.loads((base/'normal_envelope_audit.json').read_text())['rows']
    saved = json.loads((ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1/saved_scene_validation_last/report.json').read_text())
    records = {r['scene']: r for r in saved['rows'] if r['slot']=='vrm_05'}
    fresh = json.loads((base/'boundary320/report.json').read_text())
    assert saved['weights_sha256']==fresh['weights_sha256']
    shapes = []
    for s in selection:
        if s['source']=='historical':
            r=records[s['scene']]
            assert hashlib.sha256(Path(r['source_image']).read_bytes()).hexdigest()==r['image_sha256']
            polygon=np.asarray(r['primary']['polygon'])+r['crop_origin_px']
            digest=r['image_sha256']
        else:
            r=next(r for r in fresh['rows'] if Path(r['image']).stem==s['scene'])
            scene=json.loads((base/s['scene']/'scene.json').read_text())
            assert hashlib.sha256(Path(r['image']).read_bytes()).hexdigest()==r['source_sha256']
            assert scene['image_sha256']==r['source_sha256']
            polygon=np.asarray(r['samples'][0]['primary']['polygon'])+scene['crop_origin_px']
            digest=r['source_sha256']
        shapes.append(dict(**s,polygon=polygon,digest=digest))
    # One shared translation for raster storage only; never recenter individual parts.
    all_points=np.concatenate([s['polygon'] for s in shapes])
    origin=np.floor(all_points.min(0))-8
    width,height=np.ceil(all_points.max(0)-origin+9).astype(int)
    normals=[s for s in shapes if s['source']=='historical' and s['label']=='PASS']
    rows=[]
    for s in shapes:
        comparisons=[]
        for n in normals:
            if s['digest']==n['digest']:
                continue
            metric=errors(n['polygon']-origin,s['polygon']-origin,int(width),int(height))
            comparisons.append(dict(reference=n['scene'],**metric))
        nearest=min(comparisons,key=lambda r:r['boundary_p95_px'])
        rows.append(dict(scene=s['scene'],label=s['label'],source=s['source'],
            nearest_p95=nearest,best_iou=max(c['iou'] for c in comparisons),
            comparisons=comparisons,status='UNKNOWN'))
    normal_rows=[r for r in rows if r['source']=='historical' and r['label']=='PASS']
    result=dict(rows=rows,normal_nearest_p95_range=[min(r['nearest_p95']['boundary_p95_px'] for r in normal_rows),
        max(r['nearest_p95']['boundary_p95_px'] for r in normal_rows)],
        normal_best_iou_range=[min(r['best_iou'] for r in normal_rows),max(r['best_iou'] for r in normal_rows)],
        weights_sha256=saved['weights_sha256'],authority='ADVISORY_ONLY',runtime_changed=False,
        training=False,robot_command_sent=False,conveyor_command_sent=False,
        limitation='Retrospective nearest normal contour, self/source excluded. Predicted masks are not contour truth. '
                    'No per-part alignment, fitted threshold, calibrated height or acceptance claim.')
    (base/'full_contour_audit.json').write_text(json.dumps(result,indent=2))
    print('normal p95 range',result['normal_nearest_p95_range'],'IoU range',result['normal_best_iou_range'])
    for r in rows:
        if r['label']!='PASS':
            print(r['scene'],r['label'],r['nearest_p95']['boundary_p95_px'],r['best_iou'])


if __name__=='__main__':
    main()

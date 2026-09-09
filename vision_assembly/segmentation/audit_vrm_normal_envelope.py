"""Retrospective VRM5 normal-boundary envelope; not an acceptance calibration."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def excess(bounds, normals):
    normals = np.asarray(normals, dtype=float)
    bounds = np.asarray(bounds, dtype=float)
    if normals.ndim != 2 or normals.shape[1] != 4 or len(normals) < 2:
        raise ValueError('At least two normal boundaries required')
    if bounds.shape != (4,) or not np.isfinite(normals).all() or not np.isfinite(bounds).all():
        raise ValueError('Invalid bounds')
    return np.maximum(np.maximum(normals.min(0)-bounds, bounds-normals.max(0)), 0).tolist()


def main():
    base = ROOT / 'runtime/inspection/vrm_seating_pairs'
    path = ROOT / 'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1/saved_scene_validation_last/report.json'
    data = json.loads(path.read_text())
    manifest = json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    truth = {}
    for s in manifest['scenes']:
        digest = hashlib.sha256((ROOT/s['image']).read_bytes()).hexdigest()
        if s.get('image_sha256') and s['image_sha256'] != digest:
            raise ValueError('Changed manifest image')
        truth[digest] = s
    rows = []
    unavailable = []
    for r in data['rows']:
        if r['slot'] != 'vrm_05' or r['expected_pose'] not in ('PASS', 'FAIL'):
            continue
        assert hashlib.sha256(Path(r['source_image']).read_bytes()).hexdigest() == r['image_sha256']
        if r['central_candidate_count'] != 1 or r['primary'] is None:
            unavailable.append(r['scene'])
            continue
        poly = np.asarray(r['primary']['polygon']) + r['crop_origin_px']
        bounds = np.r_[poly.min(0), poly.max(0)].tolist()
        rows.append(dict(scene=r['scene'], label=r['expected_pose'], bounds=bounds,
            label_basis=truth[r['image_sha256']].get('label_source'), source='historical'))
    normals = [r for r in rows if r['label'] == 'PASS']
    envelope = [r['bounds'] for r in normals]
    for r in rows:
        # Normals are excluded from their own reference envelope.
        reference = [n['bounds'] for n in normals if n is not r]
        r['excess_px'] = excess(r['bounds'], reference)
    fresh = json.loads((base/'boundary320/report.json').read_text())
    assert fresh['weights_sha256'] == data['weights_sha256']
    for r in fresh['rows']:
        scene = json.loads((base/Path(r['image']).stem/'scene.json').read_text())
        assert r['source_sha256'] == scene['image_sha256']
        bounds = r['samples'][0]['primary']['extent_in_fixed_crop']
        offset = scene['crop_origin_px'] * 2
        bounds = (np.asarray(bounds)+offset).tolist()
        rows.append(dict(scene=scene['physical_scene_id'], label=scene['seating_label'],
            label_basis=scene['label_basis'], bounds=bounds, source='fresh',
            excess_px=excess(bounds, envelope)))
    result = dict(rows=rows, unavailable=unavailable, normal_reference_count=len(normals),
        normal_lower=np.min(envelope,axis=0).tolist(), normal_upper=np.max(envelope,axis=0).tolist(),
        edge_order=['left','top','right','bottom'], authority='ADVISORY_ONLY', status='UNKNOWN',
        limitation='Historical selected normal envelope, leave-one-out for normals; no metric wall calibration. '
                   'FAIL labels may be rotation or seating. Inside envelope does not imply PASS.',
        runtime_changed=False, training=False, robot_command_sent=False, conveyor_command_sent=False)
    (base/'normal_envelope_audit.json').write_text(json.dumps(result,indent=2))
    for r in rows:
        print(r['scene'],r['label'],r['excess_px'])


if __name__ == '__main__':
    main()

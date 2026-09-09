"""Two estimators of the SAME mask: consistency, not independent sensing."""
import json
import math
import cv2
import numpy as np
from validate_vrm_envelope_robustness import load_frames
from replay_vrm_placement_envelopes import BASE, LEFT


def axis_delta(angle, reference=90.0):
    return (angle-reference+90) % 180-90


def angles(primary):
    if primary is None:
        return None
    poly = np.asarray(primary['polygon'], np.float32)
    m = cv2.moments(poly)
    if abs(m['m00']) < 1e-6:
        return None
    cov = np.array([[m['mu20'], m['mu11']], [m['mu11'], m['mu02']]]) / m['m00']
    values, vectors = np.linalg.eigh(cov)
    if values[0] <= 0 or values[1] / values[0] < 1.1:
        return None  # Ambiguous axis; not an assembly tolerance.
    v = vectors[:, 1]
    return [axis_delta(primary['long_axis_deg']), axis_delta(math.degrees(math.atan2(v[1], v[0])))]


def main():
    output = BASE / 'rotation_evidence_audit.json'
    if output.exists():
        raise FileExistsError(output)
    frames, provenance = load_frames()
    # Earlier normal return stays normal; do not shrink the reference to left-only poses.
    normal = ['131407', '132543', *LEFT]
    estimates = {t: {s: angles(r['primary']) for s, r in f.items()} for t, f in frames.items()}
    rows = []
    for stamp in frames:
        refs = [t for t in normal if t != stamp]
        pools = {s: [estimates[t][s] for t in refs] for s in frames[stamp]}
        if any(v is None for pool in pools.values() for v in pool):
            raise ValueError('Missing reference axis')
        margins = [max(max(p[i] for p in pool)-min(p[i] for p in pool) for pool in pools.values()) for i in range(2)]
        for slot, a in estimates[stamp].items():
            bounds = [[min(p[i] for p in pools[slot]), max(p[i] for p in pools[slot])] for i in range(2)]
            signs = []
            if a is not None:
                signs = [-1 if a[i] < bounds[i][0]-margins[i] else 1 if a[i] > bounds[i][1]+margins[i] else 0 for i in range(2)]
            candidate = len(signs)==2 and signs[0]!=0 and signs[0]==signs[1]
            rows.append(dict(capture=stamp, slot=slot, normal_reference_scene=stamp in normal,
                             estimators_deg=a, reference_bounds_deg=bounds, margins_deg=margins,
                             evidence='ROTATION_CANDIDATE' if candidate else 'UNKNOWN', status='UNKNOWN'))
    summary = dict(normal_observations=sum(r['normal_reference_scene'] for r in rows),
                   normal_candidates=[r for r in rows if r['normal_reference_scene'] and r['evidence']=='ROTATION_CANDIDATE'],
                   controlled_vrm4=[r for r in rows if r['slot']=='vrm_04' and r['capture'] in ['132330','132543','141441']])
    output.write_text(json.dumps(dict(status='UNKNOWN', runtime_enabled=False, report_sha256=provenance,
        summary=summary, rows=rows,
        limitation='Development heuristic, pooled normal angular spread, no physical angular tolerance. Both estimators share a segmentation mask, not independent evidence. Leave-one-normal-scene-out. No production PASS/FAIL, no rotation normalization or historical relabeling.'), indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()

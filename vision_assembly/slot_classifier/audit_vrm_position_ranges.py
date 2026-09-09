"""Empirical normal center ranges, not engineering socket tolerances."""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main():
    manifest = json.loads((ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json').read_text())
    development = json.loads((ROOT/'runtime/inspection/vrm_outline_blur1_20260905/edges.json').read_text())
    records = {(r['stamp'],r['slot']):r for r in development['rows']}
    for stamp in ('150517','150807'):
        report = json.loads((ROOT/f'runtime/inspection/vrm_outline_blur1_holdout_{stamp}/edges.json').read_text())
        assert report['foreground_blur']==1
        records.update({(r['stamp'],r['slot']):r for r in report['rows']})
    normals, tests = {}, []
    for scene in manifest['scenes']:
        stamp = Path(scene['image']).stem.rsplit('_',1)[-1]
        for slot,expected in scene.get('expected_pose',{}).items():
            row = records.get((stamp,slot))
            if row is None or not row['grabcut']:
                continue
            item = dict(stamp=stamp,slot=slot,expected=expected,
                        center=row['grabcut']['rect'][0],
                        angle=(row['grabcut']['rect'][2]+45)%90-45)
            # Entire latest physical scene excluded, even its normal slots.
            if expected=='PASS' and stamp!='150807':
                normals.setdefault(slot,[]).append(item)
            tests.append(item)
    results = []
    for item in tests:
        refs = [r for r in normals.get(item['slot'],[]) if r['stamp']!=item['stamp']]
        if len(refs)<2:
            continue
        centers = np.array([r['center'] for r in refs])
        low,high = centers.min(axis=0),centers.max(axis=0)
        center = np.array(item['center'])
        excess = np.maximum(np.maximum(low-center,center-high),0)
        results.append(dict(**item,status='UNKNOWN',reference_stamps=[r['stamp'] for r in refs],
                            normal_min=low.tolist(),normal_max=high.tolist(),
                            outside_observed_range_px=excess.tolist()))
    output = ROOT/'runtime/inspection/vrm_position_range_audit_20260905.json'
    output.write_text(json.dumps(dict(authority='ADVISORY_ONLY',runtime_enabled=False,
        note='Leave-scene-out descriptive range; not calibrated socket tolerance. Latest scene excluded from all references.',
        robot_command_sent=False,conveyor_command_sent=False,rows=results),indent=2))
    for r in results:
        print(r['stamp'],r['slot'],r['expected'],r['outside_observed_range_px'])


if __name__=='__main__':
    main()

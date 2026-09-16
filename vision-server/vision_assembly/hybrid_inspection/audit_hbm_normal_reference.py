"""Build an isolated user-labelled normal reference and audit separate captures.

Never deploys a reference, changes thresholds, or converts UNKNOWN into PASS.
"""
import argparse
import hashlib
import json
from pathlib import Path

import cv2

from hbm_pin_bands import inspect_hbm_pins

ROOT = Path(__file__).resolve().parents[2]


def load_report(path):
    report = json.loads(path.read_text())
    if hashlib.sha256(Path(report['input_image']).read_bytes()).hexdigest() != report['input_sha256']:
        raise ValueError('Source image changed')
    if not report['registration']['alignment_valid']:
        raise ValueError('Invalid registration')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--normal-report', type=Path, required=True)
    parser.add_argument('--holdout-report', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = load_report(args.normal_report)
    held = [(p, load_report(p)) for p in args.holdout_report]
    if any(r['input_sha256'] == source['input_sha256'] for _, r in held):
        raise ValueError('Reference capture cannot be a holdout')
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = dict(reference_id='user_normal_' + args.normal_report.parent.name,
                    authority='ADVISORY_ONLY', slots={},
                    source_sha256=source['input_sha256'],
                    label_basis='User explicitly identifies current board as all normal')
    for sid in [f'hbm_{i:02}' for i in range(1, 9)]:
        crop = args.normal_report.parent / 'fixed_slots/hbm' / (sid + '.png')
        manifest['slots'][sid] = dict(path=str(crop.resolve().relative_to(ROOT)),
            sha256=hashlib.sha256(crop.read_bytes()).hexdigest())
    candidate_path = args.output / 'candidate_manifest.json'
    candidate_path.write_text(json.dumps(manifest, indent=2))
    rows = []
    for path, report in held:
        for sid in manifest['slots']:
            crop = cv2.imread(str(path.parent / 'fixed_slots/hbm' / (sid + '.png')))
            old = inspect_hbm_pins(sid, crop, 'PRESENT', True)
            new = inspect_hbm_pins(sid, crop, 'PRESENT', True, manifest_path=candidate_path)
            rows.append(dict(report=str(path), slot_id=sid,
                before=old.to_dict(), after=new.to_dict()))
    controls = []
    for sid, entry in manifest['slots'].items():
        image = cv2.imread(str(ROOT / entry['path']))
        h, w = image.shape[:2]
        damaged = image.copy()
        # Synthetic pin-band occlusion is a wiring control, not physical accuracy.
        damaged[int(.2*h):int(.68*h), int(.69*w):int(.88*w)] = 20
        result = inspect_hbm_pins(sid, damaged, 'PRESENT', True, manifest_path=candidate_path)
        controls.append(dict(slot_id=sid, evidence=result.to_dict()))
    payload = dict(rows=rows, synthetic_controls=controls, deployed=False,
        before_candidates=sum(r['before']['status'] == 'FAIL' for r in rows),
        after_candidates=sum(r['after']['status'] == 'FAIL' for r in rows),
        limitation='Related normal captures; synthetic controls do not qualify physical pin defects. UNKNOWN is not PASS.')
    (args.output / 'audit.json').write_text(json.dumps(payload, indent=2))
    print(json.dumps({k: v for k, v in payload.items() if k not in ('rows', 'synthetic_controls')}))


if __name__ == '__main__':
    main()

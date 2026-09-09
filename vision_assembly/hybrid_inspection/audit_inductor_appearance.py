"""Offline appearance audit; never updates deployed thresholds or training data."""
import json
import os
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'vision_assembly/inspection'))
from predict_component_patchcore import _checkpoint, _predict_outputs


def main():
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    out = ROOT / 'runtime/inspection/patchcore/inductor_appearance_audit_20260906'
    out.mkdir(parents=True, exist_ok=True)
    models = ROOT / 'runtime/inspection/patchcore/pcb_components_strict_v4'
    dataset = ROOT / 'vision_assembly/inspection/datasets/pcb_components_strict_v4/inductor/test'
    checkpoint = _checkpoint(models, 'inductor')
    rows = []
    for group in ['good', 'controlled_defect']:
        predictions = _predict_outputs('inductor', dataset / group, checkpoint, out / group)
        for name, result in predictions.items():
            rows.append(dict(source=str(dataset / group / (name+'.png')), group=group,
                             score=float(result['score'])))
    # Explicitly selected user-confirmed normal controls, not every unflagged slot.
    for run, slots in [
        ('20260906_183201_489371', ['inductor_01', 'inductor_02']),
        ('20260906_183249_740026', ['inductor_01', 'inductor_02']),
        ('20260906_183337_961766', ['inductor_01', 'inductor_02']),
        ('20260906_175326_427204', ['inductor_01']),
        ('20260906_184959_868834', ['inductor_01']),
    ]:
        path = ROOT / 'runtime/inspection/hybrid_fixed_slot' / run / 'hybrid_report.json'
        report = json.loads(path.read_text())
        for slot in report['slots']:
            if slot['slot_id'] in slots:
                rows.append(dict(source=str(path), slot=slot['slot_id'],
                                 group='recent_normal', score=slot['stages']['surface']['score']))
    for run in ['20260906_172537_068340', '20260906_174102_525585',
                '20260906_175326_427204', '20260906_184959_868834']:
        path = ROOT / 'runtime/inspection/hybrid_fixed_slot' / run / 'hybrid_report.json'
        report = json.loads(path.read_text())
        slot = next(s for s in report['slots'] if s['slot_id']=='inductor_02')
        rows.append(dict(source=str(path), slot='inductor_02', group='recent_direction_defect',
                         score=slot['stages']['surface']['score']))
    summary = {}
    for group in ['good', 'controlled_defect', 'recent_normal', 'recent_direction_defect']:
        values = [r['score'] for r in rows if r['group'] == group]
        summary[group] = dict(count=len(values), minimum=min(values), maximum=max(values),
                              median=float(np.median(values)))
    normal_max = max(r['score'] for r in rows if r['group'] in ['good', 'recent_normal'])
    defects = [r for r in rows if r['group'] in ['controlled_defect', 'recent_direction_defect']]
    conflicts = [r for r in defects if r['score']<=normal_max]
    defect_min = min(r['score'] for r in defects)
    payload = dict(checkpoint=str(checkpoint), rows=rows, summary=summary,
                   normal_max=normal_max, defects_at_or_below_normal_max=conflicts,
                   defect_min=defect_min, observed_gap=defect_min-normal_max,
                   misses_at_hypothetical_045=[r for r in defects if r['score']<=.45],
                   policy='AUDIT_ONLY_NO_THRESHOLD_PROMOTION',
                   warning='Same parts and related captures; controlled defects are not certified surface-crack labels. Recent normals are diagnostic, not independent calibration validation.')
    (out/'audit.json').write_text(json.dumps(payload, indent=2)+'\n')
    print(json.dumps(dict(summary=summary, normal_max=normal_max,
                         overlapping_defects=len(conflicts), report=str(out/'audit.json')), indent=2))


if __name__ == '__main__':
    main()

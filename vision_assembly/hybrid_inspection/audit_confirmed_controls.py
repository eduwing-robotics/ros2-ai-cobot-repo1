"""Read-only regression of explicitly labelled historical controls, not accuracy certification.

Uses archived provider outputs and replays only today's advisory presentation rules.
No training, inference, relabelling, camera access or production decision changes.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def controls():
    rows = []
    def add(run, slot, track, truth, provenance):
        rows.append(dict(report=f'runtime/inspection/{run}/hybrid_report.json',
                         slot=slot, track=track, truth=truth, provenance=provenance,
                         split='reused_development_control'))
    for run, truth in {
        'hybrid_fixed_slot/20260906_205818_570243': 'NORMAL',
        'hybrid_smd01_lip_worst_normal_regression/20260904_141942_759205': 'NORMAL',
        'hybrid_all_smd_recovery_full_142508/20260904_142746_328777': 'NORMAL',
        'hybrid_smd01_lip_seating_verified/20260904_141847_556412': 'DEFECT',
        'hybrid_smd_mixed_verified/20260904_144104_172098': 'DEFECT',
    }.items():
        add(run, 'smd_capacitor_01', 'seating', truth,
            'vision_assembly/hybrid_inspection/audit_pose_normal_defect_separation.py')
    for run, slots in [
        ('20260906_183201_489371', ['inductor_01', 'inductor_02']),
        ('20260906_183249_740026', ['inductor_01', 'inductor_02']),
        ('20260906_183337_961766', ['inductor_01', 'inductor_02']),
        ('20260906_175326_427204', ['inductor_01']),
        ('20260906_184959_868834', ['inductor_01']),
    ]:
        for slot in slots:
            add('hybrid_fixed_slot/' + run, slot, 'direction', 'NORMAL',
                'vision_assembly/hybrid_inspection/audit_inductor_appearance.py')
    for run in ['20260906_172537_068340', '20260906_174102_525585',
                '20260906_175326_427204', '20260906_184959_868834']:
        add('hybrid_fixed_slot/' + run, 'inductor_02', 'direction', 'DEFECT',
            'vision_assembly/hybrid_inspection/audit_inductor_appearance.py')
    return rows


def outcome(truth, status):
    """Provider-level diagnostic, never the fused production verdict."""
    if status not in ('PASS', 'FAIL'):
        return 'ABSTAIN'
    return {('NORMAL', 'PASS'): 'TN', ('NORMAL', 'FAIL'): 'FP',
            ('DEFECT', 'PASS'): 'FN', ('DEFECT', 'FAIL'): 'TP'}[(truth, status)]


def validate_image(report):
    path = Path(report['input_image'])
    if not path.is_absolute():
        path = ROOT / path
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != report.get('input_sha256'):
        raise ValueError('source_image_hash_mismatch')
    return digest


def evaluate(root=ROOT):
    from main import build_advisory_candidates
    rows, excluded, seen = [], [], set()
    for control in controls():
        try:
            report_path = root / control['report']
            report_bytes = report_path.read_bytes()
            report = json.loads(report_bytes)
            digest = validate_image(report)
            key = (digest, control['slot'], control['track'])
            if key in seen:
                raise ValueError('duplicate_image_slot_track')
            seen.add(key)
            slots = [s for s in report['slots'] if s['slot_id'] == control['slot']]
            if len(slots) != 1:
                raise ValueError('missing_or_duplicate_slot')
            slot = slots[0]
            stage_name = 'orientation' if control['track'] == 'direction' else 'pose'
            stage = slot.get('stages', {}).get(stage_name, {})
            status = stage.get('status', 'UNAVAILABLE')
            candidates = build_advisory_candidates([slot])
            codes = [code for c in candidates for code in c.get('codes', [])]
            # Generic 2-D pose cannot establish physical lip seating truth.
            metric = outcome(control['truth'], status) if control['track'] == 'direction' else 'NOT_COMPARABLE'
            rows.append(dict(**control, input_sha256=digest,
                             report_sha256=hashlib.sha256(report_bytes).hexdigest(),
                             archived_provider=stage_name, archived_status=status,
                             diagnostic_outcome=metric, current_advisory_codes=codes,
                             fused_status=report.get('status'),
                             reason=stage.get('reason'), score=stage.get('score')))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            excluded.append(dict(**control, exclusion=str(exc)))
    return dict(schema_version=1, mode='ARCHIVED_PROVIDERS_CURRENT_ADVISORY_RULES',
                independent_validation=False, current_model_accuracy_measured=False,
                source_rules_sha256=hashlib.sha256((root/'vision_assembly/hybrid_inspection/main.py').read_bytes()).hexdigest(),
                rows=rows, excluded=excluded,
                diagnostic_counts=dict(Counter(r['diagnostic_outcome'] for r in rows)),
                uncovered_tracks=['presence', 'in_plane_position', 'pins', 'surface_crack'],
                limitations=['Labels inherited from explicitly documented control audits; not newly relabelled.',
                             'No detection/heatmap is not evidence of normality.',
                             'Archived provider PASS/FAIL is not production authority.',
                             'Seating controls cannot certify generic 2-D pose.',
                             'These development captures must not be advertised as independent test accuracy.'],
                runtime_changed=False, robot_command_sent=False, conveyor_command_sent=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve each run; an existing output must be explicitly reviewed, not replaced.
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(output=str(args.output), included=len(result['rows']),
                          excluded=len(result['excluded']), counts=result['diagnostic_counts'])))


if __name__ == '__main__':
    main()

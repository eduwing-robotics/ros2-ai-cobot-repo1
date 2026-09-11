"""Replay saved pose measurements with a frozen reference, without image inference.

Archive changes are not accuracy measurements. Only explicitly labelled scenes
can be scored, and reused images are not independent tests.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from main import build_advisory_candidates
from opencv_inspectors import check_auxiliary_pose


def recheck_slots(slots, entries, geometry):
    result = deepcopy(slots)
    for slot in result:
        old = slot['stages'].get('pose', {})
        m = old.get('measured') or {}
        limits = old.get('limits') or {}
        sid = slot['slot_id']
        if not m or sid not in entries or sid not in geometry:
            continue
        # The locked sensor contract uses 1600x1266 registered board pixels
        # and a 139x110mm board. No per-component shift/rotation is fitted.
        item = dict(confidence=old['confidence'], evidence=dict(
            present=True, center_px=m['center_px'], expected_center_px=geometry[sid][:2],
            long_axis_angle_deg_undirected=m['axis_angle_deg'],
            mask_area_px=m.get('mask_area_px'),
            normalized_slot_distance=m.get('normalized_slot_distance')))
        slot['stages']['pose'] = check_auxiliary_pose(
            item, limits['expected_axis_angle_deg'], (1266, 1600, 3), (139, 110),
            position_tolerance_mm=limits['position_tolerance_mm'],
            angle_tolerance_deg=limits['angle_tolerance_deg'],
            slot_reference_offset_mm=entries[sid]['offset_mm'],
            slot_reference_calibration_id=entries[sid]['calibration_id'],
            check_axis_angle=m.get('axis_angle_checked', True)).to_dict()
    return result


def summarize(slots):
    return dict(raw_pose_fail=[s['slot_id'] for s in slots if s['stages'].get('pose', {}).get('status') == 'FAIL'],
                candidates={s['slot_id']: s['codes'] for s in build_advisory_candidates(slots)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    sample_report = Path(config['fixed_pose_reference']['samples'][-1]['report'])
    geometry = json.loads((sample_report.parent/'geometry_reference.json').read_text())['slots']
    rows = []
    skipped = []
    for path in sorted(args.root.rglob('hybrid_report.json')):
        try:
            report = json.loads(path.read_text())
            source = Path(report['input_image'])
            if hashlib.sha256(source.read_bytes()).hexdigest() != report['input_sha256']:
                raise ValueError('source hash mismatch')
            after = recheck_slots(report['slots'], config['auxiliary_pose_slot_reference_offsets_mm'], geometry)
            rows.append(dict(report=str(path), source_sha256=report['input_sha256'],
                before=summarize(report['slots']), after=summarize(after), ground_truth='UNASSIGNED'))
        except (ValueError, KeyError, TypeError, OSError) as error:
            skipped.append(dict(report=str(path), reason=type(error).__name__))
    payload = dict(purpose='COUNTERFACTUAL_ARCHIVE_NOT_NEW_INFERENCE', rows=rows, skipped=skipped,
        report_count=len(rows), unique_sources=len({r['source_sha256'] for r in rows}),
        changed_candidate_sets=sum(r['before']['candidates'] != r['after']['candidates'] for r in rows),
        limitation='Includes different historical providers and repeated images; not a qualification metric or automatic relabelling.')
    with args.output.open('x') as stream:
        json.dump(payload, stream, indent=2)
    print(json.dumps({k:v for k,v in payload.items() if k not in {'rows','skipped'}}, indent=2))


if __name__ == '__main__':
    main()

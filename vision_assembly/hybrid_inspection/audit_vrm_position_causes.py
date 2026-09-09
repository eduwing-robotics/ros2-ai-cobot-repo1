"""Separate centre-offset diagnostics from unmeasured physical wall clearance."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def describe(pose, boundary):
    m = pose.get('measured', {})
    return dict(position_error_mm=m.get('position_error_mm'),
                absolute_longitudinal_offset_mm=m.get('absolute_longitudinal_offset_mm'),
                absolute_transverse_offset_mm=m.get('absolute_transverse_offset_mm'),
                angle_error_deg=m.get('axis_angle_error_deg'),
                position_tolerance_mm=pose.get('limits', {}).get('position_tolerance_mm'),
                raw_offset_mm=m.get('raw_offset_mm'),
                slot_reference_correction_mm=m.get('slot_reference_correction_mm'),
                rightward_reference_excess_px=boundary.get('right_excess_px'),
                boundary_codes=boundary.get('codes', []),
                required_right_wall_clearance_mm=1.0,
                measured_right_wall_clearance_mm=None,
                clearance_status='UNKNOWN',
                limitation='Neither centre offset nor learned-mask rightward reference excess measures socket-wall clearance.')


def main():
    directory = ROOT/'runtime/inspection/vrm_controls_20260908'
    rows = []
    for stamp, ids in [('170142', ['vrm_02']), ('185803', ['vrm_02','vrm_03'])]:
        paths = list(directory.glob(f'extended_normal_{stamp}/*/hybrid_report.json'))
        if len(paths) != 1:
            raise ValueError('Expected unique saved report')
        report = json.loads(paths[0].read_text())
        for sid in ids:
            matches = [s for s in report['slots'] if s['slot_id'] == sid]
            if len(matches) != 1:
                raise ValueError('Expected unique slot')
            stages = matches[0]['stages']
            rows.append(dict(report=str(paths[0]), slot=sid, input_sha256=report['input_sha256'],
                             **describe(stages['pose'], stages.get('vrm_boundary', {}))))
    result = dict(rows=rows, runtime_changed=False, robot_command_sent=False,
                  conveyor_command_sent=False, policy='No threshold adjustment or label promotion')
    with (directory/'position_causes.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()

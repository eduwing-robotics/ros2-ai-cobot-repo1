"""Audit labelled SMD01 evidence; never tune thresholds or assign new labels."""
import json
from pathlib import Path
from main import build_advisory_candidates

ROOT = Path(__file__).resolve().parents[2]


def main():
    sources = {
        'hybrid_fixed_slot/20260906_205818_570243': 'normal',
        'hybrid_smd01_lip_worst_normal_regression/20260904_141942_759205': 'normal',
        'hybrid_all_smd_recovery_full_142508/20260904_142746_328777': 'normal',
        'hybrid_smd01_lip_seating_verified/20260904_141847_556412': 'seating_defect',
        'hybrid_smd_mixed_verified/20260904_144104_172098': 'seating_defect',
    }
    rows = []
    for source, truth in sources.items():
        report = json.loads((ROOT / 'runtime/inspection' / source / 'hybrid_report.json').read_text())
        slot = next(s for s in report['slots'] if s['slot_id'] == 'smd_capacitor_01')
        pose = slot['stages']['pose']
        m = pose['measured']
        candidates = build_advisory_candidates([slot])
        rows.append(dict(source=source, input_sha256=report['input_sha256'], truth=truth,
                         raw_pose=pose['status'], confidence=pose['confidence'],
                         position_mm=m['position_error_mm'],
                         transverse_mm=m['absolute_transverse_offset_mm'],
                         angle_deg=m['axis_angle_error_deg'], mask_area_px=m['mask_area_px'],
                         surface_score=slot['stages']['surface']['score'],
                         codes=candidates[0]['codes'] if candidates else []))
    metrics = {}
    for metric in ['position_mm', 'transverse_mm', 'angle_deg']:
        normal = [r[metric] for r in rows if r['truth'] == 'normal']
        defect = [r[metric] for r in rows if r['truth'] != 'normal']
        metrics[metric] = dict(normal_min=min(normal), normal_max=max(normal),
                               defect_min=min(defect), defect_max=max(defect),
                               larger_is_bad_threshold_can_separate=max(normal) < min(defect))
    payload = dict(rows=rows, metrics=metrics,
                   limitation='Five previously explicitly labelled SMD01 development scenes only. Seating is not equivalent to 2-D displacement; no fresh inference, automatic calibration, or relabelling of other slots.',
                   runtime_changed=False, robot_command_sent=False, conveyor_command_sent=False)
    out = ROOT / 'runtime/inspection/pose_normal_defect_separation_20260907.json'
    out.write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()

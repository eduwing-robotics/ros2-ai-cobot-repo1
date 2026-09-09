"""Offline, read-only evidence synthesis; not an inspection runtime provider.

Run with python3 -B vision_assembly/hybrid_inspection/audit_geometry_release.py.
Only generated artifacts under the fixed geometry release directory are written.
No image decoding, model imports, capture, network, or hardware commands.
"""
import ast
import hashlib
import json
import math
import numpy as np
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'runtime/inspection/parallel_release_20260908/geometry'
SOURCES = {
    'contract': 'vision_assembly/config/inspection_fusion_contract.json',
    'wall': 'runtime/inspection/vrm_wall_repeatability_20260908_v2/audit.json',
    'position': 'runtime/inspection/vrm_controls_20260908/position_causes.json',
    'cad': 'vision_assembly/config/unity_socket_clearance.json',
    'gripper': 'vision_assembly/config/vrm_gripper_access_requirement.json',
    'labels': 'vision_assembly/config/vrm_presence_context_holdout_20260905.json',
    'annotation': 'vision_assembly/config/vrm04_socket_wall_annotation.json',
    'config': 'vision_assembly/config/full_board_inspection.json',
    'boundary': 'vision_assembly/hybrid_inspection/vrm_boundary_advisory.py',
}


def boundary_probe(source):
    """Execute only the existing pure evaluator and literal guard, never imports."""
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'evaluate')
    guard_node = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'RIGHT_PIXEL_GUARD' for t in n.targets))
    guard = ast.literal_eval(guard_node.value)
    helpers = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('axis_limit_side', '_evaluate_valid')]
    namespace = {'RIGHT_PIXEL_GUARD': guard, 'math': math, 'np': np, 'Mapping': Mapping}
    exec(compile(ast.Module(body=helpers+[function], type_ignores=[]), '<offline-existing-evaluate>', 'exec'), namespace)
    result = namespace['evaluate'](
        {'position': [0, 0, 10], 'axes': [-89, -89]},
        [[0, 0, 10]], [[89, 89]], [0, 0, 0], [3, 3])
    return {
        'id': 'BOUNDARY_AXIAL_WRAP_FALSE_ROTATION',
        'source_line': function.lineno,
        'verification': 'SYNTHETIC_PURE_FUNCTION_ONLY',
        'reproduced': 'ROT?' in result['codes'],
        'reference_axes_deg': [89, 89], 'sample_axes_deg': [-89, -89],
        'margin_deg': [3, 3], 'axial_distance_deg': 2,
        'actual_codes': result['codes'], 'actual_status': result['status'],
        'actual_authority': result['authority'], 'right_pixel_guard_px': guard,
        'impact': 'Linear min/max comparison can emit ROT? across the +/-90 axial wrap within a 3 degree margin. No production occurrence established.',
        'action_report_only': 'Use modulo-180 axial differences around a reference with wrap-aware bounds and regression tests; do not normalize away real slot-relative rotation.',
        'runtime_edited': False,
    }


def summarize(data, probe):
    """Keep source labels, image geometry and engineering requirements distinct."""
    wall, position = data['wall'], data['position']
    cad, gripper = data['cad'], data['gripper']
    grouped = defaultdict(list)
    for row in wall['rows']:
        grouped[row['slot']].append(row['right_groove_board_x_px'])
    repeats = [{'slot': slot, 'observations': len(xs),
                'minimum_x_px': min(xs), 'maximum_x_px': max(xs),
                'range_px': max(xs) - min(xs)} for slot, xs in sorted(grouped.items())]
    scenes = data['labels']['scenes']
    diagnostics = []
    for row in position['rows']:
        matches = [s for s in scenes if s.get('image_sha256') == row.get('input_sha256')
                   and row.get('input_sha256')]
        scene = matches[0] if len(matches) == 1 else {}
        review = scene.get('process_position_review', {})
        if review.get('slot') != row['slot']:
            review = {}
        diagnostics.append({
            'source_diagnostic': row,
            'label_match': 'EXACT_IMAGE_SHA256' if scene else 'UNKNOWN_OR_AMBIGUOUS',
            'source_scene_id': scene.get('physical_scene_id'),
            'explicit_presence_label': scene.get('labels', {}).get(row['slot']),
            'explicit_expected_pose_label': scene.get('expected_pose', {}).get(row['slot']),
            'label_source': scene.get('label_source'),
            'physical_seating_label': review.get('physical_seating'),
            'process_position_review': review or None,
            'interpretation': 'Historical expected_pose labels are not runtime PASS; centre offsets and RIGHT? do not certify seating height, collision, or wall clearance.',
            'status': 'UNKNOWN', 'authority': 'ADVISORY_ONLY',
        })
    return {
        'schema_version': 1, 'scope': 'Offline geometry readiness only; not whole-board certification',
        'release_readiness': 'BLOCKED', 'status': 'UNKNOWN', 'authority': 'ADVISORY_ONLY',
        'contract_id': data['contract']['contract_id'],
        'fusion_policy_preserved': data['contract']['fusion_policy'],
        'millimetres': {
            'cad_nominal_vrm': cad['component_types']['VRM'],
            'cad_scope': 'CAD-derived dimensions, not measured printed clearance',
            'user_reported_dimensions': gripper.get('user_reported_measurement'),
            'required_entry_side_gap_mm': gripper['minimum_gap_mm'],
            'gap_between': gripper['gap_between'],
            'measured_clearance_mm': None,
            'position_uncertainty_config_mm': data['config']['measurement_uncertainty']['position_mm'],
            'uncertainty_scope': 'Existing pose configuration, not validated socket-wall uncertainty',
        },
        'pixels': {
            'wall_repeatability_recomputed': repeats,
            'source_summary_matches': all(any(s['slot'] == r['slot']
                and s['observations'] == r['observations']
                and abs(s['right_groove_range_px'] - r['range_px']) < 1e-9
                for s in wall['summary']) for r in repeats) and len(repeats) == len(wall['summary']),
            'gap_comparison': wall['gap_comparison'],
            'right_pixel_guard_px': probe['right_pixel_guard_px'],
            'limitation': wall['limitation'],
            'pixel_to_mm_conversion_performed': False,
            'vrm04_reference_annotation': data['annotation'],
        },
        'physical_seating_vs_process_position': diagnostics,
        'blockers': [
            'No calibrated per-slot inner wall/body edge at seating or gripper height; all source measured clearances are null.',
            'Only two groove observations per slot; zero repeat spread is not zero uncertainty. Dark groove may be shadow/outer rim.',
            'CAD VRM width clearance 1.0 mm and user-reported width clearance 1.5 mm have different provenance; usable travel and uncertainty remain unverified.',
            'Entry-side mapping, actual gripper thickness and collision clearance are unvalidated; the requirement is body-to-own-wall, not body-to-PM1.',
            'Explicit normal seating and requested process POSITION_ERROR coexist; no historical label rewrite or training promotion is authorized.',
            'Boundary estimators share one mask; RIGHT?/ROT? remain advisory and cannot provide calibrated PASS/FAIL.',
        ],
        'existing_bug_report_only': probe,
        'runtime_changed': False, 'training_labels_changed': False,
        'robot_command_sent': False, 'conveyor_command_sent': False,
        'capture_performed': False, 'gpu_used': False,
    }


def render(result):
    mm = result['millimetres']
    lines = ['# Offline geometry release readiness', '',
             'BLOCKED / UNKNOWN / ADVISORY_ONLY. No runtime or training-label changes.', '',
             f"CAD total XY clearance: {mm['cad_nominal_vrm']['total_clearance_mm']} mm; centre tolerance: {mm['cad_nominal_vrm']['center_tolerance_mm']} mm.",
             f"User-reported total XY clearance: {mm['user_reported_dimensions']['total_clearance_xy_mm']} mm (not certified usable travel).",
             f"Required entry-side gap: {mm['required_entry_side_gap_mm']} mm. Measured physical clearance: unavailable. No px-to-mm conversion.", '',
             '## Existing pixel evidence', '']
    for row in result['pixels']['wall_repeatability_recomputed']:
        lines.append(f"- {row['slot']}: {row['observations']} observations; groove x spread {row['range_px']:.3f} px.")
    lines += ['', '## Existing centre diagnostics and explicit labels', '']
    for item in result['physical_seating_vs_process_position']:
        row = item['source_diagnostic']
        review = item['process_position_review'] or {}
        lines.append(f"- {item['source_scene_id']} / {row['slot']}: centre error {row['position_error_mm']:.6f} mm vs {row['position_tolerance_mm']} mm pose tolerance; boundary {row['boundary_codes']}; expected_pose={item['explicit_expected_pose_label']}; physical seating={item['physical_seating_label'] or 'not explicitly specified'}; process request={review.get('user_requested_disposition', 'not specified')}. Clearance remains UNKNOWN.")
    lines += ['', '## Blockers', ''] + ['- ' + b for b in result['blockers']]
    bug = result['existing_bug_report_only']
    lines += ['', '## Existing bug (report only)', '',
              f"{bug['id']}: reproduced={bug['reproduced']}. Reference +89°, sample -89°, axial distance 2°, margin 3° emits {bug['actual_codes']}. Synthetic evaluator only; no production occurrence established. Runtime source unchanged.",
              bug['action_report_only'], '',
              'Verification: input SHA-256 provenance and offline synthetic tests; no capture, GPU, robot or conveyor commands.', '']
    return '\n'.join(lines)


def main():
    data, provenance = {}, {}
    for name, relative in SOURCES.items():
        raw = (ROOT / relative).read_bytes()
        provenance[name] = {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}
        data[name] = raw.decode() if name == 'boundary' else json.loads(raw)
    result = summarize(data, boundary_probe(data['boundary']))
    result['source_provenance'] = provenance
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, content in [('summary.json', json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'),
                          ('summary.md', render(result))]:
        path = OUTPUT / name
        path.write_text(content, encoding='utf-8')
        print(path)


if __name__ == '__main__':
    main()

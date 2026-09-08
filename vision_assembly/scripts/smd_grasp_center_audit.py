#!/usr/bin/env python3
"""Inspect SMD Base-XY correction. No ROS, motion commands, or recipe writes."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean


def vector(value, size, name):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f'{name}: expected {size} finite numbers')
    if any(isinstance(x, bool) for x in value):
        raise ValueError(f'{name}: boolean is not a coordinate')
    result = [float(x) for x in value]
    if not all(math.isfinite(x) for x in result):
        raise ValueError(f'{name}: nonfinite coordinate')
    return result


def correction_xy(recipe):
    correction = recipe['grasp_center_correction_base_mm']
    return vector([correction['x'], correction['y']], 2, 'Base correction')


def describe_center(recipe, detected_xy, planned_xy=None):
    """Expose the existing fixed Base correction, without changing a target."""
    detected = vector(list(detected_xy), 2, 'detected Base XY')
    correction = correction_xy(recipe)
    expected = [a+b for a, b in zip(detected, correction)]
    planned = None if planned_xy is None else vector(list(planned_xy), 2, 'planned TCP XY')
    difference = None if planned is None else [a-b for a, b in zip(planned, expected)]
    return {
        'schema': 'fr5.smd_grasp_center_diagnostic/v1',
        'diagnostic_only': True,
        'correction_frame': 'base',
        'formula': 'planned_tcp_xy = detected_part_xy + fixed_base_correction_xy',
        'detected_part_base_xy_mm': detected,
        'fixed_base_correction_xy_mm': correction,
        'expected_tcp_base_xy_mm': expected,
        'planned_tcp_base_xy_mm': planned,
        'plan_minus_expected_xy_mm': difference,
        'arithmetic_consistent': None if difference is None else math.hypot(*difference) <= 1e-6,
        'physical_alignment_verified': False,
        'measured_remaining_error_xy_mm': None,
    }


def compare_observations(recipe, observations):
    """Compare explicit same-context physical alignment observations; never apply them."""
    if (observations.get('schema') != 'fr5.smd_alignment_observations/v1'
            or observations.get('frame') != 'base' or observations.get('units') != 'mm'):
        raise ValueError('observations require v1 schema, Base frame and mm units')
    context_keys = ('calibration_id', 'view_id', 'tool_id')
    if any(not observations.get(k) for k in context_keys):
        raise ValueError('calibration_id, view_id and tool_id are required')
    rows = observations.get('samples')
    if not isinstance(rows, list) or not rows:
        raise ValueError('no measured alignment samples')
    seen, results = set(), []
    for row in rows:
        sample_id = row.get('sample_id')
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
            raise ValueError('sample_id must be unique and nonempty')
        seen.add(sample_id)
        if any(row.get(k, observations[k]) != observations[k] for k in context_keys):
            raise ValueError('mixed calibration/view/tool observations')
        if row.get('alignment_confirmed') is not True:
            raise ValueError('actual centered alignment must be explicitly recorded')
        detected = vector(row.get('detected_part_base_xy_mm'), 2, 'detected XY')
        aligned = vector(row.get('aligned_tcp_base_xy_mm'), 2, 'aligned TCP XY')
        abc = vector(row.get('aligned_tcp_abc_deg'), 3, 'aligned TCP ABC')
        current = describe_center(recipe, detected)
        observed_offset = [a-b for a, b in zip(aligned, detected)]
        residual = [a-b for a, b in zip(aligned, current['expected_tcp_base_xy_mm'])]
        results.append(dict(sample_id=sample_id, aligned_tcp_abc_deg=abc,
                            observed_correction_base_xy_mm=observed_offset,
                            remaining_correction_base_xy_mm=residual,
                            residual_norm_mm=math.hypot(*residual)))
    return dict(samples=results, sample_count=len(results),
                mean_remaining_correction_base_xy_mm=[mean(r['remaining_correction_base_xy_mm'][i] for r in results) for i in range(2)],
                max_residual_norm_mm=max(r['residual_norm_mm'] for r in results),
                automatically_apply=False,
                note='Residual = physically aligned TCP minus existing planned TCP; no pass threshold or new recipe is inferred.')


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipes', type=Path, default=root/'config/part_gripper_recipes.json')
    parser.add_argument('--observations', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    recipe = json.loads(args.recipes.read_text())['parts']['right_white_brown']
    record = recipe['grasp_height']
    report = dict(schema='fr5.smd_grasp_center_audit/v1', robot_commands_sent=0,
                  recipe_sha256=hashlib.sha256(args.recipes.read_bytes()).hexdigest(),
                  recipe_status=recipe.get('status'),
                  recorded_reference=describe_center(recipe, record['reference_base_xy_mm'], record['corrected_tcp_xy_mm']),
                  reference_is_independent_measurement=False,
                  observations=None,
                  missing_measurement='Fresh detected Base XY paired with physically centered TCP XY at a recorded tool, view and calibration.')
    if args.observations:
        report['observations'] = compare_observations(recipe, json.loads(args.observations.read_text()))
        report['observations_sha256'] = hashlib.sha256(args.observations.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as file:
        json.dump(report, file, ensure_ascii=False, indent=2, allow_nan=False)
        file.write('\n')
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

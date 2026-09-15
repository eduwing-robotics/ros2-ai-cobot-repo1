"""Offline occupancy-independent centroid baseline; never promotes calibration.

Fit only three previously verified historical normal reports. Replay reserved
physical scenes without adjusting offsets or tolerances on their outcomes.
"""
import hashlib
import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'vision_assembly/hybrid_inspection'))
from preprocessor_and_cropper import FixedSlotCropper, YoloSegAuxiliary


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    base = ROOT/'runtime/inspection'
    out = base/'vrm_fixed_pose_offline_20260905'
    out.mkdir(exist_ok=args.resume)
    cropper = FixedSlotCropper(ROOT/'vision_assembly/config/full_board_inspection.json')
    references = [
        base/'hybrid_vrm_pose_calibration_normal_151315/20260904_190832_071549/hybrid_report.json',
        base/'hybrid_vrm_pose_calibration_normal_151404/20260904_191202_272387/hybrid_report.json',
        base/'hybrid_vrm_pose_calibration_normal_151508/20260904_191215_159114/hybrid_report.json',
    ]
    samples = {}
    provenance = []
    for path in references:
        report = json.loads(path.read_text())
        provenance.append(dict(report=str(path), sha256=sha(path), image=report['input_image']))
        for slot in report['slots']:
            if slot['component_type'] == 'VRM':
                samples.setdefault(slot['slot_id'], []).append(slot['stages']['pose']['measured']['raw_offset_mm'])
    assert len(samples) == 5 and all(len(v) == 3 for v in samples.values())
    offsets = {k: np.median(v, axis=0).tolist() for k,v in samples.items()}
    candidate = dict(authority='ADVISORY_ONLY', runtime_enabled=False,
                     method='fixed_raw_centroid_after_board_only_registration',
                     reference_reports=provenance, offsets_mm=offsets,
                     restriction='Three repeated historical normal frames, not physical socket metrology.')
    candidate_path = out/'candidate.json'
    if candidate_path.exists():
        assert json.loads(candidate_path.read_text()) == candidate
    else:
        candidate_path.write_text(json.dumps(candidate, indent=2))
    manifest_path = ROOT/'vision_assembly/config/vrm_presence_context_holdout_20260905.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['training_allowed'] is False
    provider = YoloSegAuxiliary()
    rows = []
    for i,scene in enumerate(manifest['scenes']):
        image_path = ROOT/scene['image']
        source_hash = sha(image_path)
        if scene.get('image_sha256'):
            assert source_hash == scene['image_sha256']
        assert str(image_path) not in {p['image'] for p in provenance}
        work = out/str(i)
        work.mkdir(exist_ok=args.resume)
        registered = cropper.register(cv2.imread(str(image_path)))
        if registered.alignment_reason != 'OK':
            raise RuntimeError(f'Uncertain alignment: {image_path}')
        aligned = work/'aligned.png'
        cv2.imwrite(str(aligned), registered.image_bgr)
        cached = work/'yolo/s22_parts_seg_latest.json'
        if args.resume and cached.exists():
            saved = json.loads(cached.read_text())
            assert all(d['calibration_id'] == sha(aligned)[:16] for d in saved['detections'])
            items = {d['slot_id']: d for d in saved['detections']}
        else:
            items = provider.inspect(aligned, work/'yolo')
            if provider.last_status != 'ADVISORY_ONLY':
                raise RuntimeError(provider.last_reason)
        ppm = np.array([registered.image_bgr.shape[1]/cropper.board_size_mm[0],
                        registered.image_bgr.shape[0]/cropper.board_size_mm[1]])
        for slot, expected in scene.get('expected_pose', {}).items():
            if expected not in ('PASS', 'FAIL') or scene['labels'].get(slot) != 'PRESENT':
                continue
            item = items.get(slot, {})
            evidence = item.get('evidence', {})
            row = dict(scene=scene['physical_scene_id'], slot=slot, expected=expected,
                       image_sha256=source_hash,
                       prior_hash_available=bool(scene.get('image_sha256')),
                       status='UNKNOWN', warning=None)
            if evidence.get('present') and item.get('confidence', 0) >= .20:
                raw = (np.array(evidence['center_px'])-evidence['expected_center_px'])/ppm
                residual = raw-offsets[slot]
                error = float(np.linalg.norm(residual))
                angle = float(evidence['long_axis_angle_deg_undirected'])
                angle_error = abs((angle-90+90)%180-90)
                row.update(raw_mm=raw.tolist(), residual_mm=residual.tolist(), error_mm=error,
                           angle_error_deg=angle_error, warning=bool(error >= .70 or angle_error > 3.0))
            rows.append(row)
        (out/'progress.json').write_text(json.dumps(rows, indent=2))
        print(f'{i+1}/{len(manifest["scenes"])} {scene["physical_scene_id"]}', flush=True)
    summary = {}
    for truth in ('PASS','FAIL'):
        subset = [r for r in rows if r['expected'] == truth]
        summary[truth] = dict(count=len(subset), warnings=sum(r['warning'] is True for r in subset),
                              no_warning=sum(r['warning'] is False for r in subset),
                              unavailable=sum(r['warning'] is None for r in subset))
    result = dict(summary=summary, rows=rows, manifest_sha256=sha(manifest_path),
                  runtime_enabled=False, authority='ADVISORY_ONLY',
                  robot_command_sent=False, conveyor_command_sent=False,
                  note='Retrospective diagnostic. Pose FAIL can include out-of-plane seating; '
                       'centroid and axis alone do not cover that defect. No test-set fitting.')
    (out/'evaluation.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()

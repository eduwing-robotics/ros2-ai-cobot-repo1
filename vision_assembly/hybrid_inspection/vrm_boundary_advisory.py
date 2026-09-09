"""Frozen S22 boundary candidate. Never grants assembly PASS/FAIL authority."""
import hashlib
import json
import math
import importlib.util
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from types import SimpleNamespace
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'vision_assembly/segmentation/runs/vrm_fixed_boundary_negative_v1'
WEIGHT_HASH = '98572682b1df4aef452d7d5727c3cf6acf6abc7e6d954fdce7a214046d6f10cc'
LEFT = ['152933', '153345', '153918', '154722', '155607', '160026']
NORMAL = ['131407', '132543', *LEFT]
# Pixel-raster guard, not a physical clearance allowance. Near-boundary
# evidence remains UNKNOWN; both same-mask features must exceed this guard.
RIGHT_PIXEL_GUARD = 1.0


def axis_limit_side(value, references, margin):
    """Compare undirected axes modulo180; ambiguous reference spans abstain."""
    values = np.asarray(references, dtype=float)
    if (not len(values) or not np.isfinite(values).all() or
            not math.isfinite(value) or not math.isfinite(margin) or margin < 0):
        return 0
    anchor = values[0]
    offsets = (values-anchor+90) % 180-90
    if float(np.ptp(offsets)) >= 90:
        return 0
    current = (value-anchor+90) % 180-90
    return -1 if current < min(offsets)-margin else 1 if current > max(offsets)+margin else 0


def measure(poly, origin, confidence=0.0):
    poly = np.asarray(poly, np.float32)
    if poly.ndim != 2 or poly.shape[1] != 2 or len(poly) < 3 or not np.isfinite(poly).all():
        return None
    m = cv2.moments(poly)
    if m['m00'] <= 1e-6:
        return None
    center = [m['m10']/m['m00'], m['m01']/m['m00']]
    (_, _), (w, h), angle = cv2.minAreaRect(poly)
    if w < h:
        angle += 90
    axis = (angle - 90 + 90) % 180 - 90
    cov = np.array([[m['mu20'], m['mu11']], [m['mu11'], m['mu02']]])/m['m00']
    eigen, vectors = np.linalg.eigh(cov)
    axes = None
    if eigen[0] > 0 and eigen[1]/eigen[0] >= 1.1:
        v = vectors[:, 1]
        axes = [axis, (math.degrees(math.atan2(v[1], v[0]))) % 180 - 90]
    return dict(position=[center[0]+origin[0], center[1]+origin[1], float(poly[:, 0].max())+origin[0]],
                axes=axes, confidence=float(confidence), area=float(m['m00']),
                polygon_board=(poly+np.asarray(origin)).tolist(), center_crop=center)


def evaluate(sample, positions, rotations, position_margin, angle_margin):
    """Abstain on invalid evidence before either advisory can emit a code."""
    def numeric(value, shape):
        array = np.asarray(value)
        # Do not coerce strings, booleans, complex numbers or object arrays.
        if array.dtype.kind not in 'iuf' or array.shape != shape:
            raise ValueError('Invalid numeric shape or type')
        if any(isinstance(item, (bool, np.bool_))
               for item in np.asarray(value, dtype=object).flat):
            raise ValueError('Boolean evidence')
        array = array.astype(float)
        if not np.isfinite(array).all():
            raise ValueError('Nonfinite evidence')
        return array

    if sample is None:
        return _evaluate_valid(None, positions, rotations, position_margin, angle_margin)
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            if not isinstance(sample, Mapping):
                raise ValueError('Invalid sample mapping')
            position = numeric(sample['position'], (3,))
            axes = sample['axes']
            if axes is not None:
                axes = numeric(axes, (2,))
            positions = numeric(positions, (len(positions), 3))
            rotations = numeric(rotations, (len(rotations), 2))
            pm = numeric(position_margin, (3,))
            am = numeric(angle_margin, (2,))
            if not len(positions) or not len(rotations) or (pm < 0).any() or (am < 0).any():
                raise ValueError('Empty references or negative margins')
            checked = dict(sample, position=position, axes=axes)
            result = _evaluate_valid(checked, positions, rotations, pm, am)
            # Preserve caller-owned evidence and the existing output representation.
            result.update(measured=sample, position_margin_px=position_margin,
                          angle_margin_deg=angle_margin)
            return result
    except (KeyError, TypeError, ValueError, OverflowError, FloatingPointError):
        result = _evaluate_valid(None, [], [], [], [])
        result.update(measured=sample, reason='VRM_BOUNDARY_INVALID_INPUT')
        return result


def _evaluate_valid(sample, positions, rotations, position_margin, angle_margin):
    result = dict(status='UNKNOWN', authority='ADVISORY_ONLY', codes=[],
                  reason='VRM_BOUNDARY_UNCERTAIN', measured=sample,
                  reason_ko='판단 불확실 — 정상 판정 아님',
                  limitations='Not1mm metrology; no presence/height/PASS authority; angle estimators share one mask')
    if sample is None:
        result['reason'] = 'VRM_BOUNDARY_NOT_FOUND_OR_AMBIGUOUS'
        return result
    limits = [[min(p[i] for p in positions), max(p[i] for p in positions)] for i in range(3)]
    excess = [sample['position'][i]-limits[i][1]-position_margin[i] for i in (0,2)]
    result['right_excess_px'] = excess
    result['right_pixel_guard_px'] = RIGHT_PIXEL_GUARD
    if all(value > RIGHT_PIXEL_GUARD for value in excess):
        result['codes'].append('RIGHT?')
    if sample['axes'] is not None:
        angle_limits = [[min(p[i] for p in rotations), max(p[i] for p in rotations)] for i in range(2)]
        signs = [axis_limit_side(sample['axes'][i], [p[i] for p in rotations], angle_margin[i])
                 for i in range(2)]
        if signs[0] and signs[0] == signs[1]:
            result['codes'].append('ROT?')
        result['angle_bounds_deg'] = angle_limits
        result['angle_comparison'] = 'MODULO_180_REFERENCE_ANCHORED'
    result.update(position_bounds_px=limits, position_margin_px=position_margin, angle_margin_deg=angle_margin)
    if result['codes']:
        result['reason'] = 'VRM_BOUNDARY_' + '_AND_'.join(result['codes'])
        result['reason_ko'] = ', '.join({'RIGHT?': '우측 치우침 의심', 'ROT?': '회전 의심'}[c] for c in result['codes'])
    return result


class VrmBoundaryAdvisory:
    def inspect(self, image, slots, *, alignment_valid, enabled=True):
        vrms = [s for s in slots if s.component_type == 'VRM']
        def unavailable(reason):
            return {s.slot_id: dict(status='UNKNOWN', authority='ADVISORY_ONLY', reason=reason, codes=[]) for s in vrms}
        if not enabled or not alignment_valid:
            return unavailable('VRM_BOUNDARY_DISABLED_OR_REGISTRATION_UNCERTAIN')
        try:
            if importlib.util.find_spec('ultralytics') is None:
                # The existing production launcher uses the PatchCore environment.
                # Execute only this provider in the existing YOLO environment.
                python = ROOT / 'vision_assembly/.venv_obb/bin/python'
                with tempfile.TemporaryDirectory(prefix='ksmc_vrm_boundary_') as directory:
                    temp = Path(directory)
                    if not cv2.imwrite(str(temp/'board.png'), image):
                        raise ValueError('Cannot write worker input')
                    (temp/'slots.json').write_text(json.dumps([
                        dict(slot_id=s.slot_id, component_type=s.component_type,
                             geometry=[float(v) for v in s.geometry]) for s in vrms]))
                    completed = subprocess.run([str(python), str(Path(__file__).resolve()), '--worker', str(temp)],
                                               capture_output=True, text=True, timeout=120)
                    if completed.returncode:
                        raise RuntimeError('YOLO worker failed: ' + completed.stderr[-600:])
                    return json.loads((temp/'result.json').read_text())
            weight = BASE / 'weights/last.pt'
            if hashlib.sha256(weight.read_bytes()).hexdigest() != WEIGHT_HASH:
                raise ValueError('Frozen weight hash mismatch')
            positions = {s.slot_id: [] for s in vrms}
            rotations = {s.slot_id: [] for s in vrms}
            reference_hashes = {}
            for stamp in NORMAL:
                reference_path = BASE/f'fresh_s22_inspection_roi_20260906_{stamp}_last/report.json'
                reference_bytes = reference_path.read_bytes()
                reference_hashes[stamp] = hashlib.sha256(reference_bytes).hexdigest()
                report = json.loads(reference_bytes)
                if report['weights_sha256'] != WEIGHT_HASH:
                    raise ValueError('Reference model mismatch')
                for row in report['rows']:
                    p = row['primary']
                    if p is None:
                        raise ValueError('Reference missing')
                    value = measure(p['polygon'], row['crop_origin_px'])
                    if value is None or value['axes'] is None:
                        raise ValueError('Reference geometry ambiguous')
                    if stamp in LEFT:
                        positions[row['slot']].append(value['position'])
                    rotations[row['slot']].append(value['axes'])
            pm = [max(max(p[i] for p in v)-min(p[i] for p in v) for v in positions.values()) for i in range(3)]
            am = [max(max(p[i] for p in v)-min(p[i] for p in v) for v in rotations.values()) for i in range(2)]
            crops, origins = [], []
            for slot in vrms:
                cx, cy, w, h = slot.geometry
                cw, ch = round(w*1.5), round(h*1.5)
                x, y = round(cx-cw/2), round(cy-ch/2)
                if x < 0 or y < 0 or x+cw > image.shape[1] or y+ch > image.shape[0]:
                    raise ValueError('Fixed crop outside image')
                crops.append(image[y:y+ch, x:x+cw].copy())
                origins.append((x,y))
            from ultralytics import YOLO
            import torch
            model = YOLO(str(weight))
            predictions = model.predict(crops, imgsz=320, conf=.25, retina_masks=True,
                                        device=0 if torch.cuda.is_available() else 'cpu', verbose=False)
            output = {}
            for slot, crop, origin, prediction in zip(vrms, crops, origins, predictions):
                candidates = []
                if prediction.masks is not None:
                    for poly, conf in zip(prediction.masks.xy, prediction.boxes.conf.cpu().tolist()):
                        value = measure(poly, origin, conf)
                        if value and .2*crop.shape[1] < value['center_crop'][0] < .8*crop.shape[1] and .2*crop.shape[0] < value['center_crop'][1] < .8*crop.shape[0]:
                            candidates.append(value)
                # More than one central body is ambiguous, never silently select one.
                sample = candidates[0] if len(candidates)==1 else None
                evidence = evaluate(sample, positions[slot.slot_id], rotations[slot.slot_id], pm, am)
                evidence.update(weights_sha256=WEIGHT_HASH, central_candidates=len(candidates),
                                reference_report_sha256=reference_hashes,
                                scope='Rightward offset from left-seated references and large rotation advisory only')
                output[slot.slot_id] = evidence
            return output
        except Exception as exc:
            return unavailable(f'VRM_BOUNDARY_UNAVAILABLE:{type(exc).__name__}:{exc}')


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--worker':
        raise SystemExit('Internal worker invocation required')
    directory = Path(sys.argv[2])
    slots = [SimpleNamespace(**s) for s in json.loads((directory/'slots.json').read_text())]
    result = VrmBoundaryAdvisory().inspect(cv2.imread(str(directory/'board.png')), slots, alignment_valid=True)
    (directory/'result.json').write_text(json.dumps(result))

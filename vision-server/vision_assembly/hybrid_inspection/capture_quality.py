"""Conservative photo triage on invariant PCB pixels, not component judgement.

Provisional gross-degradation limits can request UNKNOWN/recapture, never certify
PASS. No learned input is enhanced, re-centred or modified here. Small/local
blur, shadows, lifted corners and cracks are not qualified by this check.
"""
import hashlib

import cv2
import numpy as np


POLICY = {
    'id': 's22_static_board_quality_v1', 'validated': False,
    'cell_px': 128, 'minimum_cell_pixels': 512, 'minimum_cells': 4,
    'reference_laplacian_min': 4.0,
    'severe_blur_ratio': 0.18, 'blur_contrast_max': 0.70,
    'contrast_ratio_min': 0.30, 'brightness_ratio_min': 0.35,
    'brightness_ratio_max': 2.5, 'added_clipped_fraction_max': 0.12,
}


def _hash(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def assess_capture_quality(image_bgr, reference_bgr, static_mask, *, alignment_valid=True):
    result = dict(policy=dict(POLICY), authority='ADVISORY_ONLY',
                  status='NOT_EVALUATED', blocks_decision=True,
                  recapture_recommended=True, flags=[], metrics={},
                  scope='Invariant board pixels only; no component-specific quality guarantee',
                  note='No gross issue is not PASS. Provisional photo triage; no automatic recapture.')
    if not alignment_valid:
        result['flags'] = ['BOARD_REGISTRATION_UNCERTAIN']
        return result
    if (not isinstance(image_bgr, np.ndarray) or not isinstance(reference_bgr, np.ndarray)
            or image_bgr.shape != reference_bgr.shape or image_bgr.ndim != 3 or image_bgr.size == 0
            or image_bgr.shape[2] != 3 or image_bgr.dtype != np.uint8
            or reference_bgr.dtype != np.uint8 or not isinstance(static_mask, np.ndarray)
            or static_mask.shape != image_bgr.shape[:2]):
        result['flags'] = ['QUALITY_INPUT_INVALID']
        return result
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    ref = cv2.cvtColor(reference_bgr, cv2.COLOR_BGR2GRAY)
    # Exclude stencil neighbours too, so a defect within a masked slot cannot
    # leak into the static-region Laplacian. Exclude warp/ROI outside edges.
    mask = cv2.erode((static_mask > 0).astype(np.uint8), np.ones((9, 9), np.uint8))
    mask[:8, :] = mask[-8:, :] = 0
    mask[:, :8] = mask[:, -8:] = 0
    result['reference_pixel_sha256'] = _hash(reference_bgr)
    result['static_mask_sha256'] = _hash(mask)
    selected = mask > 0
    if selected.sum() < POLICY['minimum_cell_pixels'] * POLICY['minimum_cells']:
        result['flags'] = ['INSUFFICIENT_STATIC_BOARD_PIXELS']
        return result
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    ref_lap = cv2.Laplacian(ref, cv2.CV_32F)
    blur, contrast = [], []
    step = POLICY['cell_px']
    for y in range(0, gray.shape[0], step):
        for x in range(0, gray.shape[1], step):
            box = np.s_[y:y + step, x:x + step]
            valid = selected[box]
            if valid.sum() < POLICY['minimum_cell_pixels']:
                continue
            ref_var = float(ref_lap[box][valid].var())
            ref_std = float(ref[box][valid].std())
            if ref_var < POLICY['reference_laplacian_min'] or ref_std < 2.0:
                continue
            blur.append(float(lap[box][valid].var()) / ref_var)
            contrast.append(float(gray[box][valid].std()) / ref_std)
    if len(blur) < POLICY['minimum_cells']:
        result['flags'] = ['REFERENCE_TEXTURE_INSUFFICIENT']
        return result
    current, normal = gray[selected], ref[selected]
    metrics = dict(
        cell_count=len(blur), static_pixel_count=int(selected.sum()),
        laplacian_ratio_median=float(np.median(blur)),
        contrast_ratio_median=float(np.median(contrast)),
        brightness_ratio=float(np.median(current)) / max(float(np.median(normal)), 1.0),
        added_white_clipping=float((current >= 250).mean() - (normal >= 250).mean()),
        added_black_clipping=float((current <= 3).mean() - (normal <= 3).mean()),
    )
    flags = []
    if (metrics['laplacian_ratio_median'] < POLICY['severe_blur_ratio']
            and metrics['contrast_ratio_median'] < POLICY['blur_contrast_max']):
        flags.append('GROSS_BLUR_OR_TEXTURE_LOSS')
    if metrics['contrast_ratio_median'] < POLICY['contrast_ratio_min']:
        flags.append('GROSS_CONTRAST_LOSS')
    if not POLICY['brightness_ratio_min'] <= metrics['brightness_ratio'] <= POLICY['brightness_ratio_max']:
        flags.append('GROSS_BRIGHTNESS_SHIFT')
    if max(metrics['added_white_clipping'], metrics['added_black_clipping']) > POLICY['added_clipped_fraction_max']:
        flags.append('GROSS_CLIPPING')
    result.update(status='RECAPTURE_RECOMMENDED' if flags else 'NO_GROSS_ISSUE_DETECTED',
                  blocks_decision=bool(flags), recapture_recommended=bool(flags),
                  flags=flags, metrics=metrics)
    return result


STAGE_CODES = {'presence': {'MISSING?'}, 'pose': {'POSE?', 'RIGHT?', 'ROT?', 'SEATING?'},
               'orientation': {'DIR?', 'ROT?'}, 'pins': {'PINS?'}, 'surface': {'SURFACE?'},
               'vrm_boundary': {'RIGHT?', 'ROT?'}}


def build_evidence_audit(slot_reports, candidates):
    """Retain raw FAIL evidence separately from displayed/confirmed findings."""
    shown = {row['slot_id']: set(row.get('codes', [])) for row in candidates}
    shown = {slot: {'MISSING?'} if 'MISSING?' in codes else codes for slot, codes in shown.items()}
    items = []
    for row in slot_reports:
        for name, stage in row.get('stages', {}).items():
            if not isinstance(stage, dict) or stage.get('status') != 'FAIL':
                continue
            displayed = bool(shown.get(row['slot_id'], set()) & STAGE_CODES.get(name, set()))
            items.append(dict(slot_id=row['slot_id'], stage=name,
                              raw_status=stage['status'], authority=stage.get('authority', 'UNAVAILABLE'),
                              reason=stage.get('reason'), confidence=stage.get('confidence'),
                              measured=stage.get('measured', {}), limits=stage.get('limits', {}),
                              displayed_as_candidate=displayed,
                              explanation='CANDIDATE_SHOWN' if displayed else
                              'RAW_SIGNAL_NOT_PROMOTED_BY_CANDIDATE_RULES_NOT_A_PASS'))
    return dict(raw_fail_count=len(items), undisplayed_count=sum(not r['displayed_as_candidate'] for r in items),
                items=items, note='Raw FAIL can be advisory. Hidden signal is neither PASS nor confirmed defect.')


def build_provider_health(slot_reports, *, yolo_status=None, yolo_reason=None):
    unavailable = []
    for row in slot_reports:
        for name, stage in row.get('stages', {}).items():
            if isinstance(stage, dict) and stage.get('authority') in {'UNAVAILABLE', 'INVALID', 'DISABLED'}:
                unavailable.append(dict(slot_id=row['slot_id'], stage=name,
                                        reason=stage.get('reason'), authority=stage['authority']))
    if yolo_status in {'UNAVAILABLE', 'DISABLED'}:
        unavailable.append(dict(slot_id='ALL', stage='yolo_auxiliary', reason=yolo_reason, authority=yolo_status))
    surface_missing = [r['slot_id'] for r in unavailable if r['stage'] == 'surface']
    return dict(status='INCOMPLETE' if unavailable else 'NO_UNAVAILABLE_STAGE_REPORTED',
                unavailable_count=len(unavailable), unavailable=unavailable,
                patchcore_unavailable_slots=surface_missing,
                note='Execution availability only, not model validation. Empty heatmap can mean provider unavailable, not normal.')

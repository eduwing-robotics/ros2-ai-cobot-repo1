"""Offline, uncalibrated HBM white-row evidence; never a pin-defect verdict.

API: inspect_hbm_pin_rows(rgb, strips={"left": (x0,y0,x1,y1),
"right": (...)}, reference_rgb=..., reference_reliable=True,
orientation_usable=True, angle_error_deg=0, quality_usable=True).
Rectangles are exclusive-end coordinates in the ORIGINAL registered RGB crop.
Use axis='x' for horizontal rows (side names still identify the supplied pair).
No resizing, alignment, CLAHE, morphology, learned inference, or pin counts.
Caller must establish registration, orientation (including 180 degrees), capture
quality and same-slot trustworthy reference independently. Defaults abstain.
Thresholds are synthetic engineering heuristics, not calibrated limits.
"""
from __future__ import annotations

import numpy as np


def _image_ok(image):
    return (isinstance(image, np.ndarray) and image.ndim == 3
            and image.shape[2] == 3 and min(image.shape[:2]) >= 8
            and max(image.shape[:2]) <= 2048 and image.dtype == np.uint8)


def _runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return [[int(a), int(b)] for a, b in zip(np.where(edges == 1)[0],
                                            np.where(edges == -1)[0])]


def _profile(rgb, rect, axis):
    x0, y0, x1, y1 = rect
    pixels = rgb[y0:y1, x0:x1].astype(np.float32)
    lo, hi = pixels.min(2), pixels.max(2)
    # Absolute achromatic bright evidence; no illumination normalization.
    white = (lo >= 150) & ((hi - lo) <= 55)
    reduction = 1 if axis == 'y' else 0
    profile = white.mean(axis=reduction)
    contrast = float(np.percentile(hi, 95) - np.percentile(hi, 5))
    clipped = float((lo >= 250).mean())
    reasons = []
    if contrast < 35:
        reasons.append('LOW_CONTRAST_OR_UNRESOLVED')
    if clipped > 0.35:
        reasons.append('GLARE_OR_CLIPPING')
    return dict(white_profile=profile.tolist(),
                brightness_profile=(pixels.mean(2).mean(axis=reduction) / 255).tolist(),
                white_area_fraction=float(white.mean()),
                row_coverage=float((profile >= 0.20).mean()),
                observed_white_intervals=_runs(profile >= 0.20),
                contrast_p95_p05=contrast, clipped_fraction=clipped,
                visibility='OBSERVED_WHITE_EVIDENCE' if np.any(profile >= .20)
                else 'UNRESOLVED', quality_reasons=reasons)


def inspect_hbm_pin_rows(rgb, *, strips, reference_rgb=None,
                         reference_reliable=False, orientation_usable=False,
                         angle_error_deg=None, quality_usable=False,
                         slot_id='hbm_unknown', axis='y'):
    """Return JSON-safe contract-shaped UNKNOWN evidence, without modifying input.

    Missing/collapsed-like labels describe runs of lost reference white evidence,
    not individual pins. A three-pixel minimum and 65% reduction protect small
    print variations; fine/subpixel faults can therefore be missed. No reference
    implies UNKNOWN even when both rows are visibly white. External flags must
    be actual bool True, not truthy strings or NaNs. uint8 RGB is required.
    """
    out = dict(stage_id='pins_and_surface', slot_id=str(slot_id), status='UNKNOWN',
               confidence=0.0, calibration_id=None, authority='ADVISORY_ONLY',
               evidence=dict(candidate='hbm_white_row_v1', offline_only=True,
                             diagnostic='UNKNOWN', reasons=[], sides={}))
    ev = out['evidence']
    if not _image_ok(rgb):
        ev['reasons'] = ['INVALID_RGB_UINT8_OR_BOUNDS']
        return out
    valid_rects = isinstance(strips, dict) and set(strips) == {'left', 'right'}
    if valid_rects:
        for rect in strips.values():
            if not isinstance(rect, (tuple, list)) or len(rect) != 4 or not all(
                    isinstance(v, (int, np.integer)) and not isinstance(v, bool) for v in rect):
                valid_rects = False
                break
            x0, y0, x1, y1 = rect
            if not (0 <= x0 < x1 <= rgb.shape[1] and 0 <= y0 < y1 <= rgb.shape[0]
                    and x1-x0 >= 3 and y1-y0 >= 3):
                valid_rects = False
    if not valid_rects or axis not in ('x', 'y'):
        ev['reasons'] = ['INVALID_STRIPS_OR_AXIS']
        return out
    a, b = strips['left'], strips['right']
    if max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3]):
        ev['reasons'] = ['OVERLAPPING_SIDES']
        return out
    try:
        angle_ok = (not isinstance(angle_error_deg, (bool, str))
                    and np.isfinite(float(angle_error_deg)) and abs(float(angle_error_deg)) <= 5)
    except (TypeError, ValueError, OverflowError):
        angle_ok = False
    if orientation_usable is not True or not angle_ok:
        ev['reasons'].append('ORIENTATION_UNUSABLE')
    if quality_usable is not True:
        ev['reasons'].append('CAPTURE_QUALITY_UNVERIFIED')
    ref_ok = (_image_ok(reference_rgb) and reference_rgb.shape == rgb.shape
              and reference_reliable is True)
    if not ref_ok:
        ev['reasons'].append('RELIABLE_REFERENCE_UNAVAILABLE')
    for side, rect in strips.items():
        cur = _profile(rgb, rect, axis)
        cur.update(strip_px=list(map(int, rect)), axis=axis, diagnostic='UNKNOWN',
                   deficit_intervals=[], reference_coverage=None)
        ev['sides'][side] = cur
        ref = _profile(reference_rgb, rect, axis) if ref_ok else None
        if ref is not None:
            cur['reference_coverage'] = ref['row_coverage']
            cur['reference'] = ref
        if ev['reasons'] or cur['quality_reasons'] or ref is None:
            continue
        if ref['quality_reasons'] or ref['row_coverage'] < .15:
            cur['quality_reasons'].append('REFERENCE_ROW_UNRESOLVED')
            continue
        p, r = np.array(cur['white_profile']), np.array(ref['white_profile'])
        support = r >= .20
        intervals = [run for run in _runs(support & (p < .35 * r)) if run[1]-run[0] >= 3]
        cur['deficit_intervals'] = intervals
        cur['reference_white_retained'] = float(np.minimum(p[support], r[support]).sum()
                                                 / r[support].sum())
        cur['diagnostic'] = ('MISSING_OR_COLLAPSED_LIKE_WHITE_EVIDENCE' if intervals
                             else 'NO_LARGE_ROW_DEFICIT_OBSERVED')
    diagnostics = [s['diagnostic'] for s in ev['sides'].values()]
    if 'UNKNOWN' not in diagnostics:
        ev['diagnostic'] = ('ROW_DEFICIT_CANDIDATE' if any(s['deficit_intervals']
                             for s in ev['sides'].values()) else 'NO_LARGE_ROW_DEFICIT_OBSERVED')
    return out

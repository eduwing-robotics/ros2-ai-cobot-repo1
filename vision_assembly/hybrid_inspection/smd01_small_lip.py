"""SMD01-only advisory corroboration; no physical-clearance or FAIL authority."""
import math

RULE = {
    'authority': 'ADVISORY_ONLY',
    'reference_id': 'smd01_signed_raw_y_development_20260907',
    'raw_y_min_mm': -0.706171743866015,
    'raw_y_max_mm': 0.4333002412865324,
    'nominal_margin_mm': 0.25,
    'presence_min': 0.90,
    'outline_min': 0.20,
    # Development-only corroboration: normal recovery scores .115-.129
    # overlapped the old .10 floor. Archived defect controls retained at .14.
    # Not a physical tolerance or a validated anomaly decision threshold.
    'patchcore_min': 0.14,
    'corroboration_revision': '20260908_smd01_normal_recovery_23_case_replay',
    # One canonical-image pixel is an engineering deadband, not a measured
    # uncertainty bound. This frozen rule is specific to 110mm / 1266px.
    # Experiment at1px missed a labelled subtle defect; disabled in runtime.
    'boundary_deadband_px': 0.0,
    'canonical_y_mm_per_px': 110.0 / 1266.0,
    'limitation': 'Frozen normal-envelope plus nominal margin, not socket metrology. '
                  'Sensitive to board registration; limited placement validation only.',
}


def raw_y_outside_deadband(y, deadband_px=None):
    if deadband_px is None:
        deadband_px = RULE['boundary_deadband_px']
    excess = max(RULE['raw_y_min_mm'] - y, y - RULE['raw_y_max_mm'], 0.0)
    return bool(math.isfinite(y) and excess >
                deadband_px * RULE['canonical_y_mm_per_px'])


def small_lip_candidate(row):
    if row.get('slot_id') != 'smd_capacitor_01' or row.get('component_type') != 'SMD Capacitor':
        return False
    stages = row.get('stages', {})
    presence, pose, surface = (stages.get(k, {}) for k in ('presence', 'pose', 'surface'))
    for provider in (presence, pose, surface):
        if provider.get('authority') in (None, 'UNAVAILABLE', 'INVALID', 'DISABLED'):
            return False
    if presence.get('predicted_state') != 'PRESENT':
        return False
    try:
        raw = pose['measured']['raw_offset_mm']
        if len(raw) != 2:
            return False
        x, y = map(float, raw)
        p, c, score = (float(presence['confidence']), float(pose['confidence']), float(surface['score']))
    except (KeyError, TypeError, ValueError):
        return False
    if not all(math.isfinite(v) for v in (x, y, p, c, score)):
        return False
    return bool(0 <= p <= 1 and 0 <= c <= 1 and p >= RULE['presence_min']
                and c >= RULE['outline_min'] and score >= RULE['patchcore_min']
                and raw_y_outside_deadband(y))


def independent_lip_candidate(row):
    if row.get('slot_id') != 'smd_capacitor_01' or row.get('component_type') != 'SMD Capacitor':
        return False
    stages = row.get('stages', {})
    if stages.get('pose', {}).get('reason') != 'YOLO_AUXILIARY_CANDIDATE_MISSING':
        return False
    evidence = row.get('smd01_outline_evidence') or {}
    if not evidence.get('valid') or not evidence.get('alignment_valid'):
        return False
    presence, surface = (stages.get(k,{}) for k in ('presence','surface'))
    if any(p.get('authority') in (None,'UNAVAILABLE','INVALID','DISABLED') for p in (presence,surface)):
        return False
    try:
        y = float(evidence['raw_y_mm'])
        p, score = float(presence['confidence']), float(surface['score'])
    except (KeyError, TypeError, ValueError):
        return False
    return bool(all(math.isfinite(v) for v in (y,p,score))
                and presence.get('predicted_state') == 'PRESENT'
                and RULE['presence_min'] <= p <= 1 and score >= RULE['patchcore_min']
                and raw_y_outside_deadband(y))

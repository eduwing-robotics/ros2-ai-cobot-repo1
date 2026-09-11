"""User-authorized provisional disposition; does not certify model authority."""

def decide(slots, candidates, quality, alignment_valid, health, validated_status):
    reasons = []
    ids = [s.get('slot_id') for s in slots]
    if len(ids) != 25 or len(set(ids)) != 25 or any(not x for x in ids):
        reasons.append('INCOMPLETE_SLOT_SET')
    if not alignment_valid:
        reasons.append('REGISTRATION_INVALID')
    if quality.get('blocks_decision', True):
        reasons.append('CAPTURE_QUALITY_BLOCKED')
    # The experimental seating classifier is intentionally disabled. Other
    # runtime errors must reject the board, never masquerade as no candidates.
    unavailable = [x for x in health.get('unavailable', [])
                   if not (x.get('stage') == 'seating' and
                           x.get('reason') == 'VRM_SEATING_CANDIDATE_NOT_RUNTIME_ENABLED')]
    if unavailable:
        reasons.append('PROVIDER_UNAVAILABLE')
    def present(slot):
        state = slot.get('stages', {}).get('presence', {}).get('predicted_state')
        if state in ('PRESENT', 'CORRECT', 'ROTATED'):
            return True
        # Existing independent VRM presence evidence can support provisional
        # presence only; it does not promote direction/pose model authority.
        summary = slot.get('vrm_presence_state_summary') or {}
        probability = summary.get('present_probability', 0)
        return (state == 'UNKNOWN' and slot.get('component_type') == 'VRM'
                and summary.get('presence_candidate') == 'PRESENT'
                and summary.get('conflict') is False
                and isinstance(probability, (int, float))
                and .9 <= probability <= 1.)
    if any(not present(s) for s in slots):
        reasons.append('PRESENCE_NOT_CONFIRMED')
    if candidates:
        reasons.append('DEFECT_CANDIDATE')
    if validated_status == 'FAIL':
        reasons.append('VALIDATED_FAIL')
    return dict(mode='PROVISIONAL_BINARY_V1', validated=False,
                status='FAIL' if reasons else 'PASS',
                reasons=reasons or ['NO_DISPLAYED_DEFECT_CANDIDATE'],
                limitation='Unvalidated candidate-based disposition; no candidate is not certified normality. Incomplete pin/surface calibration and disabled experimental seating are accepted limitations.')

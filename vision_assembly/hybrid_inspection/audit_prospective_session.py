"""Read-only audit of explicit held-out session targets, not release authority."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ('86580920-5d5e-43ac-af32-046943c467e6', 'ai_gpu', 'COMPONENT_MISSING'),
    ('928bbdc2-996f-479f-80f0-2aa4f0cac1cf', 'hbm_08', 'COMPONENT_MISSING'),
    ('6c8d1c38-d001-4794-919d-13e2fd4f2b84', 'power_module_01', 'COMPONENT_MISSING'),
    ('d7a50d79-f4e0-45c2-b20b-9e5016fba0ba', 'vrm_03', 'COMPONENT_MISSING'),
    ('5219339c-4bcf-45e1-b2ef-009d318bfd73', 'inductor_01', 'COMPONENT_MISSING'),
    ('14fad7b2-bc73-4635-b951-6ff235853268', 'smd_capacitor_01', 'COMPONENT_MISSING'),
    ('9fd034cb-3fc7-466b-b192-c4cc7315a339', 'ai_gpu', 'DIRECTION_ERROR'),
    ('663f387e-5e36-4f98-8c5e-038ffd229342', 'hbm_08', 'DIRECTION_ERROR'),
    ('857570d3-dac6-4824-8369-750645fb14ec', 'inductor_01', 'DIRECTION_ERROR'),
]


def audit():
    rows = []
    for iid, slot, expected in CASES:
        directory = ROOT/'runtime/inspection/api'/iid
        state = json.loads((directory/'state.json').read_text())
        event = json.loads((directory/'event.json').read_text())
        provenance = json.loads((directory/'validation_provenance.json').read_text())
        if state['inspection_id'] != iid or state['status'] != 'COMPLETED':
            raise ValueError('Incomplete or mismatched inspection')
        if provenance['training_allowed'] or provenance['release_authority']:
            raise ValueError('Unexpected evidence role')
        hashes = {}
        for key, field in [('image', 'roi_image'), ('report', 'report')]:
            path = Path(event[field]).resolve()
            if not path.is_relative_to(ROOT/'runtime/inspection'):
                raise ValueError('Unexpected artifact path')
            hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
            expected_hash = provenance.get(f'final_{key}_sha256')
            if expected_hash and hashes[key] != expected_hash:
                raise ValueError('Artifact hash mismatch')
        findings = state['result']['findings']
        rows.append(dict(inspection_id=iid, slot=slot, expected=expected,
            target_matched=any(f['slot_id'] == slot and f['primary_defect_code'] == expected for f in findings),
            other_candidates=[dict(slot=f['slot_id'], code=f['primary_defect_code']) for f in findings if f['slot_id'] != slot],
            final_decision=state['result']['decision'], hashes=hashes,
            capture_count=len(event['attempts'])))
    return dict(rows=rows, target_matches=sum(r['target_matched'] for r in rows),
        controlled_scenes=len(rows), independent_sessions=1,
        authority_promoted=False, runtime_changed=False,
        interpretation='Target-candidate agreement only, not accuracy across all slots or confirmed defect decisions. Normal false warnings are outside this defect-target count.',
        remaining=['all-slot and independent-session validation', 'SMD normal seating warning',
                   'pin/surface validation', 'calibrated capture quality'])


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))

import json
from pathlib import Path


def test_demo_scope_cannot_promote_candidates_or_drop_uncertainty():
    config = Path(__file__).resolve().parents[1] / 'config'
    scope = json.loads((config / 'inspection_demo_scope.json').read_text())
    contract = json.loads((config / 'inspection_fusion_contract.json').read_text())
    assert scope['fusion_contract'] == contract['contract_id']
    assert scope['expected_slots'] == 25
    assert not scope['runtime_authority_override']
    assert scope['excluded_result'] == 'UNKNOWN_NOT_PASS'
    assert not scope['reporting']['candidate_is_confirmed_defect']
    assert not scope['reporting']['no_candidate_is_pass']
    assert scope['unknown_workflow']['requested_max_total_attempts'] == 2
    assert not scope['unknown_workflow']['runtime_wiring_verified']
    assert scope['unknown_workflow']['after_retry'] == 'HOLD'

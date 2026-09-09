import pytest

from audit_presence_direction_release import build_summary, counts, outcome, read_json


@pytest.mark.parametrize('truth,status,expected', [
    ('NORMAL', 'PASS', 'TN'), ('NORMAL', 'FAIL', 'FP'),
    ('DEFECT', 'PASS', 'FN'), ('DEFECT', 'FAIL', 'TP'),
    ('EMPTY', 'UNKNOWN', 'ABSTAIN'), ('PRESENT', None, 'ABSTAIN'),
    ('NORMAL_POSITION', 'PASS', 'UNLABELLED'), ('EMPTY', 'FAIL', 'TP')])
def test_outcomes(truth, status, expected):
    assert outcome(truth, status) == expected


def test_non_json_rejected():
    from pathlib import Path
    with pytest.raises(ValueError, match='JSON only'):
        read_json(Path('not_an_image.png'))


def test_empty_counts():
    assert counts([])['ABSTAIN'] == 0
    assert counts([])['total'] == 0


def test_saved_evidence_cannot_release():
    result = build_summary()
    assert result['release_readiness'] == 'NOT_READY'
    assert result['independent_validated_authority_evidence'] is False
    assert result['current_runtime_equivalence_verified'] is False
    assert result['development_reuse'] is True
    archived = result['counts']['archived_provider']['direction']
    assert (archived['TN'], archived['FN'], archived['TP']) == (8, 2, 2)
    assert result['counts']['archived_provider']['presence']['total'] == 0
    for modes in result['counts'].values():
        for c in modes.values():
            assert c['total'] == sum(c[k] for k in ('TP', 'TN', 'FP', 'FN', 'ABSTAIN', 'UNLABELLED'))
    assert all(m['authority'] == 'ADVISORY_ONLY' for m in result['current_provider_metadata'])
    assert all(p['sha256'] and p['bytes'] > 0 for p in result['provenance'])

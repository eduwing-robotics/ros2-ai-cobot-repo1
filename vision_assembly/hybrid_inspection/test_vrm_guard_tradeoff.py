import pytest
from audit_vrm_guard_tradeoff import guard_flags, summarize


def test_guard_is_strict_and_requires_both_features():
    assert guard_flags([2.83, 2.]) == {'1.0': True, '2.0': False, '3.0': False, '4.0': False}
    assert not guard_flags([20., .5])['1.0']


def test_nonfinite_evidence_is_rejected():
    with pytest.raises(ValueError):
        guard_flags([float('nan'), 4.])


def test_summary_does_not_treat_unlabelled_as_normal():
    rows = [dict(intent='LEFT_SEATED', flags={'1.0': False}),
            dict(intent='RIGHT_SHIFT', flags={'1.0': True}),
            dict(intent='UNLABELLED', flags={'1.0': True})]
    assert summarize(rows, '1.0') == {'LEFT_SEATED': {'count': 1, 'flagged': 0},
                                    'RIGHT_SHIFT': {'count': 1, 'flagged': 1}}

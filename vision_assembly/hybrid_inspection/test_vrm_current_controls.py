import pytest
from audit_vrm_current_controls import presence_outcome


@pytest.mark.parametrize('truth,state,expected', [
    ('EMPTY', 'EMPTY', 'MATCH'), ('EMPTY', 'CORRECT', 'MISMATCH'),
    ('PRESENT', 'EMPTY', 'MISMATCH'), ('PRESENT', 'ROTATED', 'MATCH'),
    ('PRESENT', 'CORRECT', 'MATCH'), ('EMPTY', 'UNKNOWN', 'ABSTAIN'),
    ('PRESENT', None, 'ABSTAIN'),
])
def test_presence_is_not_pose(truth, state, expected):
    assert presence_outcome(truth, state) == expected

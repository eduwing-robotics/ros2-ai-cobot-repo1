import hashlib
import pytest
from audit_confirmed_controls import controls, outcome, validate_image


@pytest.mark.parametrize('truth,status,expected', [
    ('NORMAL', 'PASS', 'TN'), ('NORMAL', 'FAIL', 'FP'),
    ('DEFECT', 'PASS', 'FN'), ('DEFECT', 'FAIL', 'TP'),
    ('NORMAL', 'UNKNOWN', 'ABSTAIN'), ('DEFECT', 'UNAVAILABLE', 'ABSTAIN'),
])
def test_abstention_is_not_pass_or_failure(truth, status, expected):
    assert outcome(truth, status) == expected


def test_controls_have_provenance_and_no_surface_relabelling():
    rows = controls()
    assert len(rows) == 17
    assert all(r['provenance'] and r['split'] == 'reused_development_control' for r in rows)
    assert {r['track'] for r in rows} == {'direction', 'seating'}
    assert len({(r['report'], r['slot'], r['track']) for r in rows}) == len(rows)


def test_image_hash_is_checked(tmp_path):
    image = tmp_path / 'image.png'
    image.write_bytes(b'original')
    report = dict(input_image=str(image), input_sha256=hashlib.sha256(b'original').hexdigest())
    assert validate_image(report) == report['input_sha256']
    image.write_bytes(b'replaced')
    with pytest.raises(ValueError, match='hash_mismatch'):
        validate_image(report)

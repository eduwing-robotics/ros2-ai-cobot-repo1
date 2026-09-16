import hashlib
import json

import pytest

from audit_hbm_normal_reference import load_report


def make_report(tmp_path, *, valid=True, digest=None):
    image = tmp_path / 'source.png'
    image.write_bytes(b'pinned-source')
    report = tmp_path / 'hybrid_report.json'
    report.write_text(json.dumps(dict(input_image=str(image),
        input_sha256=digest or hashlib.sha256(image.read_bytes()).hexdigest(),
        registration=dict(alignment_valid=valid))))
    return report


def test_pinned_source_is_accepted(tmp_path):
    assert load_report(make_report(tmp_path))['registration']['alignment_valid']


def test_changed_source_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='Source image changed'):
        load_report(make_report(tmp_path, digest='invalid'))


def test_invalid_alignment_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='Invalid registration'):
        load_report(make_report(tmp_path, valid=False))

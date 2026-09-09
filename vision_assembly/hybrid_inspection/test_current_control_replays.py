import hashlib
import json
import pytest
from summarize_current_control_replays import summarize


def fixture(tmp_path):
    image = tmp_path / 'source.png'
    image.write_bytes(b'source')
    digest = hashlib.sha256(b'source').hexdigest()
    row = dict(track='direction', truth='NORMAL', input_sha256=digest,
               slot='inductor_01', provenance='explicit_control')
    report = dict(input_image=str(image), input_sha256=digest, status='UNKNOWN',
                  slots=[dict(slot_id='inductor_01', stages=dict(orientation=dict(status='PASS')))],
                  advisory_candidates=dict(items=[dict(slot_id='inductor_01', codes=['SURFACE?'])]))
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(report))
    return dict(rows=[row]), path


def test_join_preserves_unknown_and_separates_surface(tmp_path):
    audit, path = fixture(tmp_path)
    result = summarize(audit, [path])
    assert result['orientation_counts'] == {'PASS': 1}
    assert result['rows'][0]['fused_board_status'] == 'UNKNOWN'
    assert result['rows'][0]['advisory_codes'] == ['SURFACE?']


def test_absent_replay_not_normal(tmp_path):
    audit, path = fixture(tmp_path)
    result = summarize(audit, [])
    assert len(result['missing']) == 1
    assert result['orientation_counts'] == {}


def test_duplicate_replay_rejected(tmp_path):
    audit, path = fixture(tmp_path)
    with pytest.raises(ValueError, match='duplicate replay'):
        summarize(audit, [path, path])

from build_parallel_release_review import review_report


def test_candidates_cannot_finalize_defects():
    report = dict(status='UNKNOWN', slots=[dict(slot_id='vrm_01', stages={
        'presence':dict(status='FAIL',authority='ADVISORY_ONLY')})])
    result = review_report(report)
    assert result['reported_authoritative_failures'] == []
    assert result['production_decision'] == 'UNKNOWN'
    assert not result['provider_promotion_performed']


def test_unavailable_not_counted_as_defect():
    r = review_report(dict(slots=[dict(slot_id='hbm_01',stages={
        'pins':dict(status='UNKNOWN',authority='UNAVAILABLE')})]))
    assert len(r['unavailable']) == 1
    assert r['reported_authoritative_failures'] == []


def test_even_reported_authority_does_not_auto_release():
    r=review_report(dict(status='FAIL',slots=[dict(slot_id='gpu',stages={
        'surface':dict(status='FAIL',authority='AUTHORITATIVE')})]))
    assert len(r['reported_authoritative_failures']) == 1
    assert r['review_disposition'] == 'NOT_RELEASED'

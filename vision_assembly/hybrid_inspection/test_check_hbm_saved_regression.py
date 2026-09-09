from check_hbm_saved_regression import check


def test_empty_or_degraded_reports_cannot_pass():
    result=check({}, {})
    assert not result['regression_passed']
    assert not result['release_qualified']
    assert any('unavailable' in e for e in result['errors'])

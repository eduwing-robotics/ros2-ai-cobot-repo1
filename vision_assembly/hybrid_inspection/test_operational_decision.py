from operational_decision import decide


def check(**overrides):
    args=dict(slots=[{'slot_id':str(i),'stages':{'presence':{'predicted_state':'PRESENT'}}} for i in range(25)], candidates=[], quality={'blocks_decision':False}, alignment_valid=True, health={'unavailable':[]},validated_status='UNKNOWN')
    args.update(overrides)
    return decide(**args)


def test_provisional_pass_does_not_claim_validation():
    r=check()
    assert r['status']=='PASS' and r['validated'] is False


def test_candidates_and_quality_and_errors_reject():
    assert check(candidates=[{'slot_id':'2'}])['status']=='FAIL'
    assert check(quality={'blocks_decision':True})['status']=='FAIL'
    assert check(alignment_valid=False)['status']=='FAIL'
    assert check(health={'unavailable':[{'stage':'surface'}]})['status']=='FAIL'
    assert check(slots=[])['status']=='FAIL'
    assert check(validated_status='FAIL')['status']=='FAIL'


def test_experimental_seating_exception_is_exact():
    row={'stage':'seating','reason':'VRM_SEATING_CANDIDATE_NOT_RUNTIME_ENABLED'}
    assert check(health={'unavailable':[row]})['status']=='PASS'
    assert check(health={'unavailable':[dict(row,reason='RUNTIME_ERROR')]})['status']=='FAIL'

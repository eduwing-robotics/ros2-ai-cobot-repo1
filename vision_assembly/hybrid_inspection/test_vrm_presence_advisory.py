import pytest
from vrm_presence_advisory import corroborates_missing, inspect_context, summarize_presence_state


def evidence():
    return (dict(status='UNKNOWN', authority='ADVISORY_ONLY', confidence=.84,
                 reason='VRM_STATE_LOW_CONFIDENCE:EMPTY'),
            dict(available=True, status='UNKNOWN', authority='ADVISORY_ONLY', present_probability=.02))


def test_two_uncertain_providers_only_nominate():
    p,c = evidence()
    assert corroborates_missing(p,c)
    assert p['status'] == c['status'] == 'UNKNOWN'


@pytest.mark.parametrize('prob',[float('nan'),float('inf'),-.1,.11,1.,True,None])
def test_bad_or_disagreeing_context(prob):
    p,c = evidence(); c['present_probability']=prob
    assert not corroborates_missing(p,c)


@pytest.mark.parametrize('key,value',[('status','PASS'),('authority','INVALID'),
    ('reason','VRM_STATE_LOW_CONFIDENCE:CORRECT'),('confidence',float('nan'))])
def test_primary_cannot_be_overridden(key,value):
    p,c = evidence();p[key]=value
    assert not corroborates_missing(p,c)


def test_invalid_registration_no_model_access():
    assert inspect_context(None,[],False) == {}


def test_presence_does_not_promote_ambiguous_state():
    p,c=evidence();c['present_probability']=.999
    state=dict(predicted_state='UNKNOWN',raw_predicted_state='EMPTY')
    result=summarize_presence_state(state,c)
    assert result['presence_candidate']=='PRESENT'
    assert result['state_candidate']=='UNRESOLVED'
    assert result['conflict'] and result['status']=='UNKNOWN'
    assert state['predicted_state']=='UNKNOWN'


def test_present_rotated_does_not_become_correct():
    p,c=evidence();c['present_probability']=.999
    result=summarize_presence_state(dict(predicted_state='ROTATED',raw_predicted_state='ROTATED'),c)
    assert result['state_candidate']=='ROTATED'
    assert result['status']=='UNKNOWN'


@pytest.mark.parametrize('bad',[None,True,float('nan'),float('inf'),-1,2,'0.99'])
def test_summary_invalid_probability_abstains(bad):
    p,c=evidence();c['present_probability']=bad
    assert summarize_presence_state({},c)['presence_candidate']=='UNRESOLVED'

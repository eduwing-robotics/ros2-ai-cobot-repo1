import numpy as np
import audit_hbm_lateral_legacy as audit
from test_hbm_individual_pins import sample


def test_endpoint_loss_survives_x_only_replay(monkeypatch):
    monkeypatch.setattr(audit,'displacement',lambda *a: {'left':{'dx_px':6},'right':{'dx_px':6}})
    ref=sample()
    cur=np.zeros_like(ref)
    cur[:,6:]=sample((7,8))[:,:-6]
    before=cur.copy()
    result=audit.replay(ref,cur)
    assert result['candidate'][1]['missing_indices']==[8,9]
    assert np.array_equal(cur,before)
    assert result['status']=='UNKNOWN'


def test_unresolved_retains_baseline(monkeypatch):
    monkeypatch.setattr(audit,'displacement',lambda *a: {'left':{'dx_px':None},'right':{'dx_px':6}})
    result=audit.replay(sample(),sample((7,8)))
    assert not result['applied']
    assert result['candidate']==result['baseline']

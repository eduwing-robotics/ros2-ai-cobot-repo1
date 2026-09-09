import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from probe_vrm_robust_edges import fit_candidates, measure


def test_line_with_outlier_bands():
    samples=[(y,[(round(30+.1*y),10.)]) for y in range(20,101,10)]
    samples[2]=(40,[(90,15.)])
    samples[6]=(80,[(10,15.)])
    r=fit_candidates(samples)
    assert r['status']=='UNKNOWN'
    assert not r['ambiguous']
    assert abs(r['candidate']['slope']-.1)<.01
    assert r['candidate']['support']==7


def test_two_equal_edges_are_ambiguous():
    r=fit_candidates([(y,[(30,10.),(40,10.)]) for y in range(20,101,10)])
    assert r['reason']=='COMPETING_LINES'


def test_blank_is_not_a_boundary():
    image=np.zeros((200,160,3),np.uint8)
    original=image.copy()
    for e in measure(image,True):
        assert e['reason']=='INSUFFICIENT_LINE_SUPPORT'
    np.testing.assert_array_equal(image,original)

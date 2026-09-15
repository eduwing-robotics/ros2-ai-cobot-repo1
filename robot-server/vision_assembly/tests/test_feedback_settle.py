import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from feedback_settle import FeedbackSettle

def test_continuous_samples_required():
    g=FeedbackSettle()
    assert not any(g.update(i,i*.1,True) for i in range(10))
    assert g.update(10,1.,True)

def test_repeated_cached_sample_cannot_pass():
    g=FeedbackSettle()
    assert not g.update(1,0,True)
    assert not g.update(1,2,True)

def test_invalid_feedback_resets():
    g=FeedbackSettle()
    for i in range(10):g.update(i,i*.1,True)
    assert not g.update(10,1.,False)
    assert not g.update(11,1.1,True)

def test_gap_resets():
    g=FeedbackSettle()
    for i in range(10):g.update(i,i*.1,True)
    assert not g.update(10,2.,True)

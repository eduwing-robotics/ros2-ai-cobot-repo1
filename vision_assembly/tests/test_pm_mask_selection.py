import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pm_mask_selection import priority
QUALITY=dict(minimum_detection_confidence=.7,minimum_mask_shape_score=.6,minimum_rectangularity=.6)
def rectangle(w,h):return np.array([[0,0],[w,0],[w,h],[0,h]],np.float32)
def test_usable_mask_beats_low_confidence_perfect_aspect():
    assert priority(.85,rectangle(21,100),5,2000,QUALITY)>priority(.12,rectangle(20,100),5,2000,QUALITY)
def test_bad_shape_does_not_win_by_confidence_alone():
    assert priority(.8,rectangle(20,100),5,2000,QUALITY)>priority(.99,rectangle(20,20),5,2000,QUALITY)

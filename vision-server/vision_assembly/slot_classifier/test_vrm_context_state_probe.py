import numpy as np
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_vrm_context_state_probe import views, evaluate


def test_fixed_views_preserve_input_and_have_no_pose_fit():
    rgb=np.arange(256*256*3,dtype=np.uint8).reshape(256,256,3)
    before=rgb.copy()
    a,b=views(rgb)
    assert a.shape==(95,95,3) and b.shape==(225,225,3)
    assert np.array_equal(a,rgb[80:175,80:175])
    assert np.array_equal(rgb,before)
    a[:]=0
    assert np.array_equal(rgb,before)


def test_bad_shape_rejected():
    with pytest.raises(ValueError): views(np.zeros((224,224,3),np.uint8))


def test_argmax_is_not_thresholded_success():
    class Candidate:
        classes_=np.array(['correct','empty','rotated'])
        def predict_proba(self,x):
            return np.array([[.89,.01,.10],[.05,.93,.02],[.95,.03,.02]])
    result=evaluate(Candidate(),np.zeros((3,1)),['correct','empty','rotated'])
    assert result['correct_at_090']==1
    assert result['wrong_at_090']==1
    assert result['abstained']==1

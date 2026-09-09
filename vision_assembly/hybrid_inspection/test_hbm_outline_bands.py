import numpy as np
import pytest
from audit_hbm_outline_bands import outline_bands


def test_bands_follow_original_coordinates_without_mutation():
    p=np.array([[30,20],[65,25],[70,80],[35,75]],float)
    old=p.copy()
    bands=outline_bands((100,100),p)
    assert np.array_equal(p,old)
    assert not (bands["left"] & bands["right"]).any()
    assert bands["left"][40,32] and bands["right"][40,66]
    assert not bands["left"][0].any()


@pytest.mark.parametrize("p", [[[0,0],[2,0],[2,40]],[[30,20],[60,20],[float("nan"),70]],
                             [[30,20],[60,20],[120,70]],[[30,20],[60,20]]])
def test_invalid_or_clipped_outline_abstains(p):
    with pytest.raises(ValueError):outline_bands((100,100),p)

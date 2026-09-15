import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from validate_vrm_boundary_scenes import summarize_mask


def test_primary_center():
    poly=np.float32([[30,20],[70,20],[70,80],[30,80]])
    row=summarize_mask(poly,.7,100,100)
    np.testing.assert_allclose(row['center_px'],[50,50])
    assert row['central_candidate']
    assert row['area_px']==2400


def test_neighbor_not_primary():
    poly=np.float32([[30,90],[70,90],[70,99],[30,99]])
    assert not summarize_mask(poly,.9,100,100)['central_candidate']


def test_degenerate_polygon():
    assert summarize_mask(np.float32([[10,10],[20,20],[30,30]]),.8,100,100) is None

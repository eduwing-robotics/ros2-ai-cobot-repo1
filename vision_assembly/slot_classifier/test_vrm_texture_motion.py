"""Synthetic checks validate measurement conventions, not PCB accuracy."""
import cv2
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))

from audit_vrm_texture_motion import texture_motion


@pytest.mark.parametrize('angle,dx,dy', [(0,0,0),(7,8,-5),(-11,-7,4)])
def test_known_texture_motion(angle,dx,dy):
    rng = np.random.default_rng(28)
    gray = rng.integers(0,255,(180,160),dtype=np.uint8)
    gray = cv2.GaussianBlur(gray,(3,3),.8)
    source = cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR)
    matrix = cv2.getRotationMatrix2D((79.5,89.5),angle,1)
    matrix[:,2] += (dx,dy)
    moved = cv2.warpAffine(source,matrix,(160,180))
    original = moved.copy()
    result = texture_motion(source,moved,(100,120))
    assert abs(result['angle_deg']-angle)<=1
    assert abs(result['dx_px']-dx)<=1
    assert abs(result['dy_px']-dy)<=1
    assert result['status']=='UNKNOWN'
    np.testing.assert_array_equal(moved,original)


def test_blank_texture_cannot_supply_pose():
    image = np.zeros((180,160,3),np.uint8)
    result = texture_motion(image,image,(100,120))
    assert result['status']=='UNKNOWN'
    assert result['reason']=='TEXTURE_TOO_WEAK'

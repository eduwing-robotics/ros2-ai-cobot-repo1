import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_vrm_fixed_crop_dataset import polygon_transform,split_scenes,clip_polygon


def test_inverse_ecc_label_mapping():
    points=np.float32([[10,20],[30,20],[30,40]])
    source=np.eye(3);source[:2,2]=[5,7]
    warp=np.float32([[1,0,2],[0,1,3]])
    np.testing.assert_allclose(polygon_transform(points,source,warp),points+[3,4])


def test_scene_split_deterministic_no_overlap():
    names=['a','b','a','c','d','e','f','g']
    split=split_scenes(names)
    assert split==split_scenes(list(reversed(names)))
    assert list(split.values()).count('test')==1
    assert list(split.values()).count('val')==1
    assert list(split.values()).count('train')==5


def test_neighbor_clipping():
    p=np.float32([[10,90],[30,90],[30,120],[10,120]])
    clipped=clip_polygon(p,100,100)
    assert clipped[:,1].max()==99
    assert clipped[:,1].min()==90
    assert len(clip_polygon(p+[200,0],100,100))==0

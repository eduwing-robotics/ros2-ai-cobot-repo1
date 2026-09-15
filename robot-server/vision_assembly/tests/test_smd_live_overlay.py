import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from smd_live_overlay import describe_detections


def box(width,height):
    return {'box':np.array([[0,0],[width,0],[width,height],[0,height]],np.float32),'confidence':.9}


def test_bad_axis_retains_current_box_and_other_valid_parts():
    rows=describe_detections([box(10,12.7)]+[box(10,20) for _ in range(4)],np.eye(3),1.35)
    assert len(rows)==5 and [r['instance_index'] for r in rows]==[1,2,3,4,5]
    assert rows[0]['axis_valid'] is False and 'too square' in rows[0]['reason']
    assert 'terminal_axis_source_pixel' not in rows[0]
    assert all(r['axis_valid'] for r in rows[1:])
    assert all(r['visualization_only'] and len(r['polygon_source_pixel'])==4 for r in rows)


def test_missing_consumed_prefix_preserves_identity_and_source_coordinates():
    H=np.array([[1.,0.,100.],[0.,1.,50.],[0.,0.,1.]])
    rows=describe_detections([None,box(10,20)],H,1.35)
    assert rows[0]['instance_index']==2
    assert rows[0]['polygon_source_pixel'][0]==[100.,50.]

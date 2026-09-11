"""Exercise real detector stabilization without loading ROS or GPU models."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import numpy as np
import cv2

def test_fifty_parts_keep_centers_types_and_frame_support():
    path=Path(__file__).resolve().parents[1]/'scripts/detect_tray_parts.py'
    tree=ast.parse(path.read_text())
    methods=[m for c in tree.body if isinstance(c,ast.ClassDef) for m in c.body
             if isinstance(m,ast.FunctionDef) and m.name in ('stabilize','order_part_instances')]
    env={'cv2':cv2,'np':np}
    exec(compile(ast.Module(body=methods,type_ignores=[]),str(path),'exec'),env)
    counts={'gpu':2,'hbm':16,'long_orange':8,'black_block':10,'marked_white':4,'right_white_brown':10}
    history=[]
    for frame in range(40):
        parts=[]
        for kind,count in counts.items():
            for i in range(count):
                # Different types intentionally share centers; never merge them.
                parts.append(dict(part_type=kind,display_name=kind,
                    reference_center_pixel=[80.+i*100+(frame%2)*2,100.],
                    camera_xyz_m=[i*.01,0.,1.],angle_deg=0.,
                    cad_area_match_score=.9,shape_score=.95,rectangularity=.95))
        history.append((frame,parts))
    node=NS(history=history,a=NS(track_radius_px=40,min_stable_hits=2),
        bins=[dict(part_spec_id=k,expected_count=v) for k,v in counts.items()])
    node.order_part_instances=lambda *a:env['order_part_instances'](node,*a)
    result=env['stabilize'](node,np.eye(3),1,1,0,0,
        {'robot_pose':None,'depth':np.zeros((1080,1920))})
    assert len(result)==50
    for kind,count in counts.items():
        group=[d for d in result if d['part_type']==kind]
        assert len(group)==count
        assert sorted(d['reference_center_pixel'][0] for d in group)==[81.+i*100 for i in range(count)]
        assert all(d['observation_frames']==40 for d in group)

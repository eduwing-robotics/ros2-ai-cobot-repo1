"""Select the first physical tray set using fixed registered reference regions."""
from copy import deepcopy
import json
import math
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1]/'config/tray_cycle_set_selection.json'

def select_cycle_tray_set(payload, config=None):
    config=json.loads(CONFIG.read_text()) if config is None else config
    if config['set_index'] != 1:
        raise RuntimeError('only reviewed tray cycle set 1 is supported')
    width=config['reference_image_size_px']['width']
    height=config['reference_image_size_px']['height']
    margin=config['boundary_margin_px']
    selected=[]
    counts={}
    for kind,rule in config['parts'].items():
        group=[d for d in payload['stable_detections'] if d.get('part_type')==kind]
        if len(group)>rule['capacity']:
            raise RuntimeError(f'{kind}: tray capacity exceeded')
        chosen=[]
        for detection in group:
            point=detection.get('reference_center_pixel')
            if not isinstance(point,(list,tuple)) or len(point)!=2 or not all(math.isfinite(float(v)) for v in point):
                raise RuntimeError(f'{kind}: invalid registered reference center')
            x,y=map(float,point)
            polygon=rule['section_polygon_normalized']
            if not (min(p[0] for p in polygon)*width <= x <= max(p[0] for p in polygon)*width
                    and min(p[1] for p in polygon)*height <= y <= max(p[1] for p in polygon)*height):
                raise RuntimeError(f'{kind}: reference center outside configured section')
            position=x if rule['axis']=='x' else y
            if abs(position-rule['boundary_px'])<=margin:
                raise RuntimeError(f'{kind}: ambiguous physical set boundary')
            if position<rule['boundary_px']:
                chosen.append(deepcopy(detection))
        if len(chosen)>rule['per_set_count']:
            raise RuntimeError(f'{kind}: extra detections inside selected set')
        # Preserve source IDs. Local indices are assigned only within fixed set 1;
        # capture retry binds actual cells geometrically once the set is complete.
        if kind in ('hbm','long_orange'):
            ordered=[]
            by_y=sorted(chosen,key=lambda d:d['reference_center_pixel'][1])
            for i in range(0,len(by_y),2):
                ordered.extend(sorted(by_y[i:i+2],key=lambda d:d['reference_center_pixel'][0]))
        else:
            ordered=sorted(chosen,key=lambda d:d['reference_center_pixel'][0])
        for i,d in enumerate(ordered,1):
            d['detector_instance_index']=d['instance_index']
            d['instance_index']=i
            d['assembly_set_index']=1
        selected.extend(ordered)
        counts[kind]={'visible':len(group),'selected':len(ordered)}
    if any(d.get('part_type') not in config['parts'] for d in payload['stable_detections']):
        raise RuntimeError('unexpected tray part type')
    result=deepcopy(payload)
    result['stable_detections']=selected
    result['assembly_set_selection']={'set_index':1,'counts':counts,'config':config}
    return result

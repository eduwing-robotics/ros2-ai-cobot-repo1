"""Persistent observation IDs independent of compacted planner instance indices.

Reference-frame centres identify tray cells, not proof of an object's physical
identity. Ambiguous association produces no binding, never a guessed match.
"""
import math
from uuid import uuid4


class TraySourceIdentity:
    def __init__(self, maximum_distance_px=12.):
        self.maximum_distance_px = maximum_distance_px
        self.cells = []

    def assign(self, detections):
        choices = []
        for detection in detections:
            point = detection.get('reference_center_pixel')
            if (not isinstance(point, (tuple,list)) or len(point)!=2
                    or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in point)):
                choices.append(None); continue
            candidates = [i for i,cell in enumerate(self.cells)
                if cell['part_type']==detection['part_type'] and
                math.dist(cell['point'],point)<=self.maximum_distance_px]
            choices.append(candidates)
        uses = {}
        for candidates in choices:
            if candidates is not None:
                for index in candidates: uses[index]=uses.get(index,0)+1
        for detection,candidates in zip(detections,choices):
            detection['id'] = None
            if candidates is None: continue
            if len(candidates)==1 and uses[candidates[0]]==1:
                # Keep the anchor fixed: incremental drift must not walk one ID
                # across adjacent cells or silently change a consumed identity.
                detection['id']=self.cells[candidates[0]]['id']
            elif not candidates:
                # Reject same-frame ambiguous new cells too.
                nearby=sum(1 for other in detections if other['part_type']==detection['part_type']
                    and isinstance(other.get('reference_center_pixel'),(list,tuple))
                    and len(other['reference_center_pixel'])==2
                    and all(isinstance(x,(int,float)) and math.isfinite(x) for x in other['reference_center_pixel'])
                    and math.dist(other['reference_center_pixel'],detection['reference_center_pixel'])<=self.maximum_distance_px)
                if nearby!=1: continue
                identifier=f"{detection['part_type']}:{uuid4()}"
                self.cells.append(dict(id=identifier,part_type=detection['part_type'],
                    point=list(detection['reference_center_pixel'])))
                detection['id']=identifier
        return detections

"""One synchronized refinement window; stale fits never authorize completion."""
import numpy as np
from fixed_cycle_snapshot import validate_tray_detection_quality
from vrm_edge_refinement import measure, summarize


class RecaptureRequired(RuntimeError):
    """Before any pick, discard the entire coarse capture and measure again."""


def matched_evidence(images, infos, stamp_ns, *, after, now):
    if not after < stamp_ns/1e9 <= now or now-stamp_ns/1e9 >= 2:
        return None
    def stamp(message):
        return message.header.stamp.sec*10**9+message.header.stamp.nanosec
    image=next((m for m in reversed(images) if stamp(m)==stamp_ns),None)
    info=next((m for m in reversed(infos) if stamp(m)==stamp_ns),None)
    if image is None or info is None:
        return None
    return image,info


class VrmRefinementWindow:
    def __init__(self,snapshot,quality):
        self.coarse={p['instance_index']:p for p in snapshot['tray_capture']['parts'] if p['part_type']=='black_block'}
        if set(self.coarse)!={1,2,3,4,5}:raise RuntimeError('VRM coarse count mismatch')
        self.quality=quality
        self.samples={i:[] for i in self.coarse}
        self.accepted={};self.anchors={};self.reasons={};self.current=set();self.last_stamp=None

    def pending(self):
        return {i:self.reasons.get(i,'collecting distinct matched frames') for i in self.coarse
                if i not in self.accepted or i not in self.current}

    def observe(self,image,payload,k,transform):
        stamp=payload['timestamp_ros_ns']
        if stamp==self.last_stamp:return False
        self.last_stamp=stamp
        self.current=set()
        ds={d['instance_index']:d for d in payload['stable_detections'] if d['part_type']=='black_block'}
        if set(ds)!=set(self.coarse):
            self.samples={i:[] for i in self.coarse};self.anchors.clear()
            return False
        for i,d in ds.items():
            # A weak detection cannot establish geometry change or valid presence.
            try:validate_tray_detection_quality(d,self.quality)
            except RuntimeError as error:
                self.samples[i]=[];self.anchors.pop(i,None);self.reasons[i]=str(error)
                continue
            pixel=np.linalg.norm(np.array(d['reference_center_pixel'])-self.coarse[i]['reference_center_pixel'])
            if pixel>12:raise RuntimeError(f'VRM-{i:02} physical cell identity changed')
            delta=np.array(d['base_xyz_mm'])-self.coarse[i]['base_xyz_mm']
            if np.linalg.norm(delta)>2:
                raise RecaptureRequired(f'VRM-{i:02} coarse geometry changed; dXYZ={delta.round(3).tolist()}mm')
            try:
                result=measure(image,d,k,transform)
                if i in self.accepted:
                    delta=np.array(result['center_base_mm'])-self.accepted[i]['base_xyz_mm']
                    angular=abs((result['base_angle_deg']-self.accepted[i]['long_axis_angle_base_deg']+90)%180-90)
                    if np.linalg.norm(delta)>2 or angular>3:
                        raise RecaptureRequired(f'VRM-{i:02} refined geometry changed; dXYZ={delta.round(3).tolist()}mm, axis={angular:.3f}deg')
                else:
                    if i not in self.anchors:self.anchors[i]=d['base_xyz_mm']
                    if np.linalg.norm(np.array(d['base_xyz_mm'])-self.anchors[i])>=1.5:
                        raise ValueError('VRM center moved during window')
                    result['timestamp']=stamp/1e9;self.samples[i].append(result)
                    if len(self.samples[i])==12:
                        self.accepted[i]=summarize(self.samples[i])
                        self.accepted[i]['refinement_captured_unix']=stamp/1e9
                self.current.add(i);self.reasons.pop(i,None)
            except RecaptureRequired:raise
            except (ValueError,RuntimeError) as error:
                self.samples[i]=[];self.anchors.pop(i,None);self.reasons[i]=str(error)
        return len(self.accepted)==5 and self.current==set(self.coarse)

"""TrayHome four-edge geometry used by the September 7 physical VRM trials."""
import copy
import cv2
import numpy as np

SOURCE = 'vrm_four_edge_v1'


def measure(image, detection, k, transform):
    if image.shape[:2] != (720, 1280):
        raise ValueError('VRM edge fit requires calibrated 1280x720 image')
    cx, cy = np.rint(detection['center_pixel']).astype(int)
    if not (24 <= cx < 1256 and 24 <= cy < 696):
        raise ValueError('VRM ROI outside image')
    g = cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(float), (3, 3), .7)
    dx = np.gradient(g, axis=1)
    fits = []
    def peak(values):
        index = int(values.argmax())
        if not 0 < index < len(values)-1:
            raise ValueError('edge peak at ROI boundary')
        den = values[index-1]-2*values[index]+values[index+1]
        return index + (.5*(values[index-1]-values[index+1])/den if abs(den)>1e-6 else 0)
    for lo, hi, sign in [(cx-17,cx-3,-1), (cx+3,cx+18,1)]:
        yy = np.arange(cy-9,cy+10)
        xs = np.array([lo+peak(sign*dx[y,lo:hi]) for y in yy])
        keep = np.ones(len(yy),bool)
        for _ in range(3):
            if keep.sum()<14: raise ValueError('too few side-edge inliers')
            slope, intercept = np.polyfit(yy[keep],xs[keep],1)
            err = xs-(slope*yy+intercept)
            keep = abs(err)<max(.4,3*np.median(abs(err)))
        if keep.sum()<14 or np.std(err[keep])>=.2:
            raise ValueError('side-edge residual too large')
        fits.append((np.degrees(np.arctan2(1,slope)),slope*cy+intercept))
    width = fits[1][1]-fits[0][1]
    angle = float(np.mean([f[0] for f in fits]))
    if abs(fits[0][0]-fits[1][0])>=1.5 or not 18<width<26 or not 70<angle<110:
        raise ValueError('VRM side-edge geometry rejected')
    dy = np.gradient(g,axis=0)
    horizontal = []
    for lo,hi,sign in [(cy-23,cy-6,-1),(cy+6,cy+24,1)]:
        columns = np.arange(cx-6,cx+7)
        rows = [lo+peak(sign*dy[lo:hi,x]) for x in columns]
        slope,intercept = np.polyfit(columns,rows,1)
        if np.std(np.array(rows)-(slope*columns+intercept))>=.3:
            raise ValueError('end-edge residual too large')
        horizontal.append((slope,intercept))
    center_x = float(np.mean([f[1] for f in fits]))
    ends = [a*center_x+b for a,b in horizontal]
    if not 20<ends[1]-ends[0]<38:
        raise ValueError('VRM end-edge separation rejected')
    center = np.array([center_x,float(np.mean(ends))])
    delta = center-np.array(detection['center_pixel'])
    if np.linalg.norm(delta)>=2:
        raise ValueError('four-edge center differs from detector by >=2px')
    k = np.asarray(k,dtype=float)
    transform = np.asarray(transform,dtype=float)
    depth = float(detection['depth_m'])
    if k.shape != (9,) or transform.shape != (4,4) or not np.isfinite(k).all() or not np.isfinite(transform).all() or not .1<depth<1 or min(k[0],k[4])<=0:
        raise ValueError('invalid calibrated projection')
    base = np.array(detection['base_xyz_mm']) + transform[:3,:3] @ (np.r_[delta/[k[0],k[4]],0]*depth*1000)
    rad = np.deg2rad(angle)
    axis = transform[:3,:3] @ np.array([np.cos(rad)/k[0],np.sin(rad)/k[4],0])
    return dict(center_base_mm=base.tolist(), center_pixel=center.tolist(),
                base_angle_deg=float(np.degrees(np.arctan2(axis[1],axis[0]))),
                image_angle_deg=angle, width_pixel=float(width))


def summarize(samples):
    if len(samples)!=12: raise ValueError('VRM refinement requires 12 frames')
    angles=np.array([x['base_angle_deg'] for x in samples])
    centers=np.array([x['center_base_mm'] for x in samples])
    if not np.isfinite(angles).all() or not np.isfinite(centers).all() or np.ptp(angles)>=1 or np.max(np.linalg.norm(centers-centers[0],axis=1))>=1.5:
        raise ValueError('VRM refinement unstable')
    return dict(base_xyz_mm=np.median(centers,axis=0).tolist(),
                long_axis_angle_base_deg=float(np.median(angles)), angle_source=SOURCE,
                position_source=SOURCE, center_correction_applied=False,
                refinement_frame_count=12, refinement_angle_span_deg=float(np.ptp(angles)))


def merge(snapshot, refinements, captured_unix):
    if set(refinements)!={1,2,3,4,5}: raise ValueError('all five VRM refinements required')
    result=copy.deepcopy(snapshot)
    parts=[p for p in result['tray_capture']['parts'] if p['part_type']=='black_block']
    if {p['instance_index'] for p in parts}!={1,2,3,4,5}: raise ValueError('VRM snapshot indices mismatch')
    for part in parts:
        refined=refinements[part['instance_index']]
        if refined.get('angle_source')!=SOURCE or refined.get('refinement_frame_count')!=12:
            raise ValueError('unvalidated VRM refinement')
        part['coarse_base_xyz_mm']=part['base_xyz_mm']
        part['coarse_long_axis_angle_base_deg']=part['long_axis_angle_base_deg']
        part.update(refined)
    result['vrm_refinement_capture']=dict(captured_unix=captured_unix,method=SOURCE,instances=[1,2,3,4,5])
    return result

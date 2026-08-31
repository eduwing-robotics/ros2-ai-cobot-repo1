#!/usr/bin/env python3
"""Capture one stable tray-part target for a non-contact hover test."""
import argparse, json, math, time
from pathlib import Path
import numpy as np

def median_axis_deg(values):
    radians=np.deg2rad(np.asarray(values,float)*2.0)
    return float(np.rad2deg(math.atan2(np.median(np.sin(radians)),np.median(np.cos(radians))))/2.0)

SET_SIZES={"black_block":5,"marked_white":2,"right_white_brown":5,"hbm":8,"long_orange":4}
EXPECTED_COUNTS={"gpu":2,"black_block":10,"marked_white":4,"right_white_brown":10,"hbm":16,"long_orange":8}

def physical_order(part,items):
    x=lambda d:float(d["reference_center_pixel"][0])
    y=lambda d:float(d["reference_center_pixel"][1])
    if part=="gpu": return sorted(items,key=x)
    if part in ("black_block","marked_white","right_white_brown"):
        size=SET_SIZES[part]; by_y=sorted(items,key=y); ordered=[]
        for start in range(0,len(by_y),size): ordered.extend(sorted(by_y[start:start+size],key=x))
        return ordered
    if part in ("hbm","long_orange"):
        size=SET_SIZES[part]; by_x=sorted(items,key=x); ordered=[]
        for start in range(0,len(by_x),size):
            one_set=sorted(by_x[start:start+size],key=y)
            for row in range(0,len(one_set),2): ordered.extend(sorted(one_set[row:row+2],key=x))
        return ordered
    return sorted(items,key=lambda d:(y(d),x(d)))

def required_visible_count(part,index):
    expected=EXPECTED_COUNTS.get(part,index)
    size=SET_SIZES.get(part,expected)
    return min(expected,((index-1)//size+1)*size)

def main():
    root=Path(__file__).resolve().parents[1]
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=root/"data/tray_detections_last.json")
    p.add_argument("--output",type=Path,default=root/"data/vrm_hover_target.json")
    p.add_argument("--part-type",default="black_block")
    p.add_argument("--display-name",default="VRM")
    p.add_argument("--instance-index",type=int)
    p.add_argument("--expected-base-x-mm",type=float)
    p.add_argument("--expected-base-y-mm",type=float)
    p.add_argument("--max-expected-distance-mm",type=float,default=15.0)
    p.add_argument("--samples",type=int,default=6)
    p.add_argument("--timeout-sec",type=float,default=20.0)
    p.add_argument("--max-position-span-mm",type=float,default=2.0)
    p.add_argument("--max-angle-span-deg",type=float,default=8.0)
    p.add_argument("--min-confidence",type=float,default=.70)
    a=p.parse_args()
    if (a.expected_base_x_mm is None)!=(a.expected_base_y_mm is None):
        p.error("--expected-base-x-mm and --expected-base-y-mm must be provided together")
    end=time.monotonic()+a.timeout_sec; seen=set(); samples=[]; last_reason="waiting for detector JSON"
    while time.monotonic()<end and len(samples)<a.samples:
        try:
            payload=json.loads(a.input.read_text(encoding="utf-8"))
            stamp=int(payload["timestamp_ros_ns"])
            if stamp in seen: time.sleep(.1); continue
            seen.add(stamp)
            if payload.get("tray_registration")!="TRACKING": raise ValueError("tray is not TRACKING")
            if payload.get("base_transform_status")!="VALID_COORDINATES_ONLY": raise ValueError(f"base transform: {payload.get("base_transform_status")}")
            instant=[d for d in payload.get("detections",[]) if d.get("part_type")==a.part_type]
            stable=[d for d in payload.get("stable_detections",[]) if d.get("part_type")==a.part_type]
            if a.expected_base_x_mm is not None:
                candidates=[]
                for item in stable:
                    point=np.asarray(item.get("base_xyz_mm",[]),float)
                    if point.shape!=(3,) or not np.all(np.isfinite(point)):continue
                    distance=float(np.linalg.norm(point[:2]-np.array([
                        a.expected_base_x_mm,a.expected_base_y_mm],float)))
                    candidates.append((distance,item))
                if not candidates:raise ValueError(f"no stable {a.display_name} near expected Base XY")
                distance,d=min(candidates,key=lambda pair:pair[0])
                if distance>a.max_expected_distance_mm:
                    raise ValueError(f"nearest {a.display_name} is {distance:.2f} mm from expected Base XY")
            elif a.instance_index is None:
                if len(instant)!=1 or len(stable)!=1: raise ValueError(f"exactly one {a.display_name} required; instant={len(instant)}, stable={len(stable)}")
                d=stable[0]
            else:
                matches=[d for d in stable if int(d.get("instance_index",-1))==a.instance_index]
                if len(instant)<a.instance_index or len(matches)!=1: raise ValueError(f"{a.display_name} instance {a.instance_index} unavailable; instant={len(instant)}, stable_matches={len(matches)}")
                d=matches[0]
                required=required_visible_count(a.part_type,a.instance_index)
                if len(stable)<required: raise ValueError(f"{a.display_name} physical-order validation needs {required} stable instances; got {len(stable)}")
                physical=physical_order(a.part_type,stable)
                if a.instance_index>len(physical): raise ValueError(f"physical index {a.instance_index} unavailable")
                expected=physical[a.instance_index-1]
                selected_px=np.asarray(d["reference_center_pixel"],float)
                expected_px=np.asarray(expected["reference_center_pixel"],float)
                if float(np.linalg.norm(selected_px-expected_px))>1.0:
                    raise ValueError(f"{a.display_name} index mismatch: reported={a.instance_index} selected_ref={selected_px.tolist()} physical_ref={expected_px.tolist()}")
            if float(d.get("median_cad_area_match_score",0))<a.min_confidence: raise ValueError(f"{a.display_name} confidence is too low")
            xyz=np.asarray(d["base_xyz_mm"],float); angle=float(d["long_axis_angle_base_deg"])
            if xyz.shape!=(3,) or not np.all(np.isfinite(xyz)) or not math.isfinite(angle): raise ValueError("invalid target coordinate")
            pixel=np.asarray(d.get("center_pixel",[np.nan,np.nan]),float)
            camera=np.asarray(d.get("camera_xyz_m",[np.nan,np.nan,np.nan]),float)
            samples.append((xyz,angle,stamp,pixel,camera)); print(f"stable sample {len(samples)}/{a.samples}: xyz={np.round(xyz,3).tolist()} angle={angle:.3f}")
        except (OSError,KeyError,TypeError,ValueError,json.JSONDecodeError) as exc:
            last_reason=str(exc)
        time.sleep(.1)
    if len(samples)<a.samples: raise RuntimeError(f"target capture timed out: {last_reason}")
    xyzs=np.asarray([s[0] for s in samples]); span=np.ptp(xyzs,axis=0); angles=[s[1] for s in samples]; center_angle=median_axis_deg(angles)
    angle_errors=np.abs([((v-center_angle+90)%180)-90 for v in angles]); angle_span=float(np.max(angle_errors)*2)
    if float(np.max(span))>a.max_position_span_mm: raise RuntimeError(f"{a.display_name} Base coordinate unstable: span={np.round(span,3).tolist()} mm")
    if angle_span>a.max_angle_span_deg: raise RuntimeError(f"{a.display_name} angle unstable: span={angle_span:.3f} deg")
    pixels=np.asarray([s[3] for s in samples],float);cameras=np.asarray([s[4] for s in samples],float)
    result={"schema_version":1,"mode":"single_part_hover_target","timestamp_unix":time.time(),"part_type":a.part_type,"display_name":a.display_name,"instance_index":a.instance_index,"selection_mode":"nearest_expected_base_xy" if a.expected_base_x_mm is not None else ("instance_index" if a.instance_index is not None else "single_instance"),"part_center_base_mm":np.round(np.median(xyzs,axis=0),3).tolist(),"long_axis_angle_base_deg":round(center_angle,3),"center_pixel":np.round(np.median(pixels,axis=0),3).tolist(),"center_pixel_span":np.round(np.ptp(pixels,axis=0),3).tolist(),"camera_xyz_m":np.round(np.median(cameras,axis=0),6).tolist(),"sample_count":len(samples),"position_span_mm":np.round(span,3).tolist(),"angle_span_deg":round(angle_span,3),"hover_offset_mm":100.0,"robot_motion_authorized":False,"source_file":str(a.input)}
    a.output.parent.mkdir(parents=True,exist_ok=True); tmp=a.output.with_suffix(".tmp"); tmp.write_text(json.dumps(result,indent=2),encoding="utf-8"); tmp.replace(a.output)
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()

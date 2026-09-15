import json,time,hashlib,math
from pathlib import Path
root=Path('/home/juchan-yoon/FR5_robot_control')
m=json.loads((root/'vision_assembly/data/smd05_operator_target_20260906.json').read_text())
fresh_path=Path('/tmp/smd05_post4_fresh_20260906.json');p=json.loads(fresh_path.read_text())
held=json.loads((root/'vision_assembly/data/smd04_pick_attempt_20260906.json').read_text())
assert held.get('physical_grasp_verified') and held.get('placement_completed')
assert p['validation_passed'] and p['instance_index']==5 and p['operator_confirmed_consumed_prefix_count']==4
assert 0<=time.time()-p['timestamp_unix']<30
assert p['handeye_sha256']==m['handeye_sha256']==hashlib.sha256((root/'calibration/data/handeye_result.json').read_bytes()).hexdigest()
assert m['manual_source_sha256']==hashlib.sha256((root/'vision_assembly/data/smd45_manual_axes_20260906.json').read_bytes()).hexdigest()
xy_error=math.dist(p['part_center_base_mm'][:2],m['part_center_base_mm'][:2]);angle_error=abs((p['long_axis_angle_base_deg']-m['long_axis_angle_base_deg']+90)%180-90)
assert xy_error<.5 and angle_error<8,(xy_error,angle_error)
m.update(timestamp_unix=p['timestamp_unix'],operator_confirmed_consumed_prefix_count=4,manual_target_original_resolved_unix=m['timestamp_unix'],current_scene_validation=dict(source_file=str(fresh_path),automatic_validation_passed=True,manual_to_current_model_center_distance_mm=xy_error,manual_to_current_model_axis_difference_deg=angle_error,source_sha256=hashlib.sha256(fresh_path.read_bytes()).hexdigest()),automatic_detection_validation_passed=True)
out=root/'vision_assembly/data/smd05_operator_target_revalidated_20260906.json';out.write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(m),flush=True)

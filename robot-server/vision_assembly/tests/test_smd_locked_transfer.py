import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
executor=pytest.importorskip('execute_full_fixed_cycle')


@pytest.mark.parametrize('pick_c',[-14.0,-4.928,-2.0,0.3,2.0,14.0])
def test_cap01_uses_one_positive_staged_transfer_with_fixed_endpoints(pick_c):
    item=dict(slot_code='CAP-01',part_type='right_white_brown',
        pick_final_tcp=[-628,-163,-52.177,-180,0,pick_c],
        place_final_tcp=[80,-559,87,-180,0,-178.7],
        placement_orientation={'mode':'align_actual_carried_axis_to_current_slot_axis'})
    route=executor.build_tcp_route([item],[-528,-121,78,180,0,90],350,resume_after_grasp=False)
    middle=[w for _,w in route if w.label=='place_combined_xy_abc_midpoint']
    assert middle
    assert all(w.tcp[2]==350 and w.tcp[3]==-180 and w.tcp[4]==0 for w in middle)
    angles=[pick_c]+[w.tcp[5] for w in middle]+[181.3]
    assert all(0 < b-a <= 60.000001 for a,b in zip(angles,angles[1:]))
    assert next(w.tcp for _,w in route if w.label=='pick_final_50mm_vertical')==tuple(item['pick_final_tcp'])
    assert next(w.tcp for _,w in route if w.label=='place_final_50mm_vertical')==tuple(item['place_final_tcp'])

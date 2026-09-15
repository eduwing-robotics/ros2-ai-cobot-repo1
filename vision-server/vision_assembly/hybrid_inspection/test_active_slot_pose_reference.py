from types import SimpleNamespace
from active_slot_pose_reference import bind_active_slot_centers


def test_reference_only_preserves_measured_center_and_input():
    item={'s':{'evidence':{'center_px':[15,20],'expected_center_px':[1,2]}}}
    result=bind_active_slot_centers(item,[SimpleNamespace(slot_id='s',geometry=(10,11,3,4))])
    assert result['s']['evidence']['center_px']==[15,20]
    assert result['s']['evidence']['expected_center_px']==[10,11]
    assert result['s']['evidence']['original_expected_center_px']==[1,2]
    assert item['s']['evidence']['expected_center_px']==[1,2]


def test_missing_detection_not_invented():
    assert bind_active_slot_centers({},[SimpleNamespace(slot_id='s',geometry=(10,11,3,4))])=={}

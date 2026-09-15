import copy
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from merge_smd_retry_captures import merge_captures


def capture(stamp, failed):
    return dict(timestamp_unix=stamp, mode='smd_close_multiframe_base_targets',
        set_index=1, required_count=5, layout_capacity=10, handeye_sha256='a'*64,
        model_sha256='b'*64, operator_confirmed_consumed_prefix_count=0,
        validation_passed=False, parts=[dict(instance_index=i, physical_instance_index=i,
            part_type='right_white_brown', center_correction_applied=False,
            part_center_base_mm=[i*10,0,0], samples=[dict(pose=[0]*6) for _ in range(24)],
            frame_count=24, temporal_batch_count=3, confidence_median=.9,
            center_span_canonical_px=[1,1], angle_batch_span_deg=1,
            validation_passed=i!=failed) for i in range(1,6)])


def test_preserves_validated_parts_and_oldest_source_time():
    a,b=capture(100,2),capture(110,1)
    result=merge_captures([('a',a),('b',b)],120)
    assert result['validation_passed']
    assert result['timestamp_unix']==100
    assert result['retry_sources']['1']['file']=='a'
    assert result['retry_sources']['2']['file']=='b'
    assert not a['validation_passed'] and not b['validation_passed']


@pytest.mark.parametrize('change', ['missing','stale','part_move','robot_move','calibration'])
def test_rejects_unsafe_retry_combinations(change):
    a,b=capture(100,2),capture(110,1)
    now=120
    if change=='missing': b['parts'][1]['validation_passed']=False
    if change=='stale': now=231
    if change=='part_move': b['parts'][0]['part_center_base_mm'][0]+=1
    if change=='robot_move': b['parts'][0]['samples'][0]['pose'][0]=1
    if change=='calibration': b['model_sha256']='c'*64
    with pytest.raises(RuntimeError): merge_captures([('a',a),('b',b)],now)


def test_different_axis_geometry_versions_cannot_be_merged():
    a,b=capture(100,2),capture(110,1)
    b['axis_geometry_version']='source_image_v1'
    with pytest.raises(RuntimeError,match='identity/calibration changed'):
        merge_captures([('a',a),('b',b)],120)

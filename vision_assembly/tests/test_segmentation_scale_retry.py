import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from segmentation_scale_retry import merge_scale_retry
Q={'minimum_detection_confidence':.7,'minimum_mask_shape_score':.6,'minimum_rectangularity':.6}
def part(x=0,score=.3,**kwargs):
 return dict(center_pixel=[x,0],segmentation_confidence=score,mask_shape_score=.9,rectangularity=.9,angle_deg=0,bbox_size_px=[10,40],depth_m=.484,**kwargs)
def merge(a,b):return merge_scale_retry(a,b,Q,primary_size=960,alternate_size=640)
def test_replaces_only_weak_matching_detection():
 good=part(30,.9);weak=part();alt=part(1,.95)
 result=merge([good,weak],[part(30,.99),alt])
 assert result[0] is good
 assert result[1]['scale_retry']['primary_confidence']==.3
 assert result[1]['center_pixel']==[1,0]
@pytest.mark.parametrize('field,value',[('center_pixel',[4,0]),('angle_deg',4),('bbox_size_px',[10,60]),('depth_m',.49),('segmentation_confidence',.69),('mask_shape_score',.59),('rectangularity',.59),('segmentation_confidence',float('nan'))])
def test_rejects_disagreement_or_bad_quality(field,value):
 a=part();b=part(1,.95);b[field]=value
 assert merge([a],[b])[0] is a
def test_ambiguous_and_missing_identities_not_added():
 a=part();b=part(2)
 assert merge([a,b],[part(1,.95)])==[a,b]
 assert merge([], [part(1,.95)])==[]
 assert merge([a],[part(1,.95),part(2,.95)])[0] is a

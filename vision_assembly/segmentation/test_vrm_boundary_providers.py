import pytest
from compare_vrm_boundary_providers import compare


def row():
    return dict(scene='s',slot='vrm_01',image_sha256='hash',central_candidate_count=1,
        crop_origin_px=[10,20],primary=dict(polygon=[[1,1],[11,1],[11,11],[1,11]]))


def test_agreement_is_not_pass():
    out=compare(row(),row())
    assert out['max_edge_difference_px']==0
    assert out['status']=='UNKNOWN' and not out['geometry_validated']


def test_missing_boundary_not_missing_part():
    out=compare(row(),dict(row(),primary=None,central_candidate_count=0))
    assert out['presence_verdict']=='UNKNOWN'
    assert out['reason']=='BOUNDARY_UNAVAILABLE_NOT_ABSENCE'


def test_distinct_candidates_remain_ambiguous():
    assert compare(row(),dict(row(),unique_central_count=2))['reason']=='AMBIGUOUS_BOUNDARY'


def test_origin_and_displacement_are_preserved():
    out=compare(row(),dict(row(),crop_origin_px=[13,20]))
    assert out['edge_difference_px']==[3,0,3,0]


def test_identity_mismatch_rejected():
    with pytest.raises(ValueError):
        compare(row(),dict(row(),image_sha256='different'))

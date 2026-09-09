import pytest
from vrm_duplicate_masks import deduplicate


def box(x=10, confidence=.8):
    return dict(polygon=[[x,10],[x+60,10],[x+60,90],[x,90]],
                confidence=confidence,extent_in_fixed_crop=[x,10,x+60,90])


def test_identical_duplicate_keeps_highest():
    a,b=box(confidence=.3),box(confidence=.8)
    unique,groups=deduplicate([a,b],100,110)
    assert unique==[b] and groups==[[1,0]]


def test_different_socket_edge_preserved():
    unique,groups=deduplicate([box(),box(13)],100,110)
    assert len(unique)==2


def test_single_empty_and_malformed():
    assert deduplicate([],100,110)==([],[])
    assert len(deduplicate([box()],100,110)[0])==1
    with pytest.raises(ValueError):
        deduplicate([dict(box(),polygon=[[float('nan'),0],[1,1],[2,2]])],100,110)

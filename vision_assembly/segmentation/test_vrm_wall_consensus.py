from probe_vrm_wall_consensus import shared_candidates


def test_multiple_candidates_not_collapsed():
    result=shared_candidates([{'x':151},{'x':163}],[{'x':149},{'x':163}])
    assert len(result)==2


def test_unmatched_and_empty():
    assert shared_candidates([{'x':151}],[{'x':178}])==[]
    assert shared_candidates([],[])==[]

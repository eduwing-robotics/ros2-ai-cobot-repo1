from vrm_boundary_advisory import axis_limit_side, evaluate


def test_wrap_is_two_degrees_not_178():
    assert axis_limit_side(-89,[89],3) == 0
    assert axis_limit_side(89,[-89],3) == 0


def test_real_wrapped_rotation_kept():
    assert axis_limit_side(-80,[89],3) == 1
    assert axis_limit_side(80,[-89],3) == -1


def test_normal_small_axes_unchanged():
    assert axis_limit_side(8,[-2,0,2],3) == 1
    assert axis_limit_side(-8,[-2,0,2],3) == -1
    assert axis_limit_side(4,[-2,0,2],3) == 0


def test_full_evaluator_no_false_wrapped_candidate():
    sample=dict(position=[0,0,0], axes=[-89,-89])
    r=evaluate(sample,[[0,0,0]],[[89,89]],[0,0,0],[3,3])
    assert 'ROT?' not in r['codes']
    assert r['status'] == 'UNKNOWN'

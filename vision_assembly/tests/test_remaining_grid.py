import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from capture_remaining_non_smd import bind_leading_empty_grid

def points(xy):return [dict(reference_center_pixel=p) for p in xy]

def test_hbm_missing_first_does_not_shuffle_rows():
    d=points([[1200,640],[1120,720],[1200,715],[1120,795],[1200,790],[1120,875],[1200,870]])
    result=bind_leading_empty_grid('hbm',list(reversed(d)))
    assert [p for p,i in result]==d
    assert [i for p,i in result]==list(range(2,9))

def test_pm_missing_first():
    d=points([[1150,250],[1060,460],[1150,455]])
    assert [p for p,i in bind_leading_empty_grid('long_orange',d)]==d

def test_wrong_empty_cell_rejected():
    with pytest.raises(RuntimeError,match='right cell'):
        bind_leading_empty_grid('long_orange',points([[1060,250],[1060,460],[1150,455]]))

def test_missing_row_member_rejected():
    with pytest.raises(RuntimeError,match='pattern'):
        bind_leading_empty_grid('hbm',points([[1200,640],[1120,720],[1200,715]]))

def test_vrm_left_to_right():
    d=points([[680,210],[750,216],[810,215],[880,214]])
    assert [p for p,i in bind_leading_empty_grid('black_block',d[::-1])]==d

def test_columns_too_close_rejected():
    with pytest.raises(RuntimeError,match='ambiguous'):
        bind_leading_empty_grid('black_block',points([[680,210],[690,210],[810,210],[880,210]]))

def test_hbm_two_consumed_preserves_three_to_eight():
    d=points([[1120,720],[1200,715],[1120,795],[1200,790],[1120,875],[1200,870]])
    result=bind_leading_empty_grid('hbm',d[::-1],2)
    assert [p for p,i in result]==d
    assert [i for p,i in result]==list(range(3,9))

def test_hbm_two_consumed_rejects_remaining_seven():
    with pytest.raises(RuntimeError,match='pattern'):
        bind_leading_empty_grid('hbm',points([[1200,640],[1120,720],[1200,715],[1120,795],[1200,790],[1120,875],[1200,870]]),2)

def test_invalid_consumed_prefix_rejected():
    with pytest.raises(RuntimeError,match='prefix'):
        bind_leading_empty_grid('long_orange',[],2)

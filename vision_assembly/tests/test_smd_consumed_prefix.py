import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from smd_set_selection import select_smd_set

LAYOUT = dict(set_count=2, parts_per_set=5, required_count=10,
              canonical_y_ranges=[[0, 50], [50, 100]])

def test_confirmed_prefix_preserves_physical_instance_two():
    parts = [{'center': [x, 20]} for x in [50, 20, 40, 30]]
    other_row = [{'center': [10, 70]}]
    result = select_smd_set(parts + other_row, LAYOUT, 1, consumed_prefix_count=1)
    assert result[0] is None
    assert result[1]['center'] == [20, 20]
    assert len(result) == 5

@pytest.mark.parametrize('count', [3, 5])
def test_unexpected_remaining_count_is_rejected(count):
    with pytest.raises(RuntimeError, match='requires 4'):
        select_smd_set([{'center': [x, 20]} for x in range(count)], LAYOUT, 1,
                       consumed_prefix_count=1)

def test_missing_part_without_confirmation_is_rejected():
    with pytest.raises(RuntimeError, match='requires 5'):
        select_smd_set([{'center': [x, 20]} for x in range(4)], LAYOUT, 1)

@pytest.mark.parametrize('prefix', [-1, 5, True, 1.5])
def test_invalid_prefix_is_rejected(prefix):
    with pytest.raises(RuntimeError, match='consumed'):
        select_smd_set([], LAYOUT, 1, consumed_prefix_count=prefix)

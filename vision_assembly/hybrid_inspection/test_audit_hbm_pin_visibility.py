import numpy as np
import pytest

from audit_hbm_pin_visibility import simulate_gain


def test_identity_and_no_mutation():
    source = np.array([[[0, 128, 255]]], dtype=np.uint8)
    before = source.copy()
    assert np.array_equal(simulate_gain(source, 1), source)
    assert np.array_equal(simulate_gain(source, .5), [[[0, 64, 128]]])
    assert np.array_equal(source, before)


@pytest.mark.parametrize("gain", [0, -1, 1.1, float("nan"), float("inf")])
def test_invalid_gain(gain):
    with pytest.raises(ValueError):
        simulate_gain(np.zeros((2, 2, 3), np.uint8), gain)

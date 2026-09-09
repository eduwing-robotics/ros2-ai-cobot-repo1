#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys

import pytest


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from vrm_state_dataset import state_labels  # noqa: E402
from vrm_state_common import crop_vrm_state_slot  # noqa: E402

import numpy as np


SLOTS = {f"vrm_{index:02d}" for index in range(1, 6)}


def test_three_state_labels_are_explicit() -> None:
    labels = state_labels(SLOTS, {"vrm_01"}, {"vrm_04"})
    assert labels == {
        "vrm_01": "empty",
        "vrm_02": "correct",
        "vrm_03": "correct",
        "vrm_04": "rotated",
        "vrm_05": "correct",
    }


def test_state_labels_reject_overlap() -> None:
    with pytest.raises(ValueError, match="both empty and rotated"):
        state_labels(SLOTS, {"vrm_03"}, {"vrm_03"})


def test_state_labels_reject_unknown_slot() -> None:
    with pytest.raises(ValueError, match="Unknown VRM slots"):
        state_labels(SLOTS, {"vrm_99"}, set())


def test_shared_vrm_crop_is_square_and_deterministic() -> None:
    image = np.arange(300 * 400 * 3, dtype=np.uint8).reshape(300, 400, 3)
    first = crop_vrm_state_slot(image, (200.25, 150.75, 90.0, 120.0))
    second = crop_vrm_state_slot(image, (200.25, 150.75, 90.0, 120.0))
    assert first.shape == (256, 256, 3)
    assert np.array_equal(first, second)

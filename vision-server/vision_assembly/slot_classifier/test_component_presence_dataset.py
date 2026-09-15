#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from component_presence_common import crop_component_presence_slot  # noqa: E402
from component_presence_dataset import presence_labels  # noqa: E402


SLOTS = {"ai_gpu", "hbm_01", "power_module_01", "inductor_01", "smd_capacitor_01"}


def test_presence_labels_require_only_explicit_empty_slots() -> None:
    labels = presence_labels(SLOTS, {"hbm_01", "inductor_01"})
    assert labels["hbm_01"] == "empty"
    assert labels["inductor_01"] == "empty"
    assert labels["ai_gpu"] == "present"


def test_presence_labels_reject_unknown_slot() -> None:
    with pytest.raises(ValueError, match="Unknown non-VRM slots"):
        presence_labels(SLOTS, {"vrm_01"})


def test_component_presence_crop_is_deterministic_square() -> None:
    image = np.arange(300 * 400 * 3, dtype=np.uint8).reshape(300, 400, 3)
    first = crop_component_presence_slot(
        image, (200.25, 150.75, 80.0, 120.0), "hbm"
    )
    second = crop_component_presence_slot(
        image, (200.25, 150.75, 80.0, 120.0), "hbm"
    )
    assert first.shape == (256, 256, 3)
    assert np.array_equal(first, second)

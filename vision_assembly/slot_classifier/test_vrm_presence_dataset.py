#!/usr/bin/env python3
"""Offline tests for explicit VRM presence dataset generation."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from vrm_presence_dataset import OUTPUT_SIZE, crop_slot, load_vrm_slots  # noqa: E402


PROJECT_DIR = Path(__file__).resolve().parents[2]


def test_layout_contains_five_vrm_slots() -> None:
    slots = load_vrm_slots(
        PROJECT_DIR / "vision_assembly/config/full_board_inspection.json",
        (1266, 1600, 3),
    )
    assert [slot["slot_id"] for slot in slots] == [
        "vrm_01",
        "vrm_02",
        "vrm_03",
        "vrm_04",
        "vrm_05",
    ]


def test_crop_has_fixed_classifier_shape() -> None:
    image = np.zeros((1266, 1600, 3), dtype=np.uint8)
    image[500:700, 600:900] = (15, 80, 220)
    crop = crop_slot(image, (750.0, 600.0, 200.0, 140.0), 0.24)
    assert crop.shape == (OUTPUT_SIZE[1], OUTPUT_SIZE[0], 3)
    assert tuple(int(value) for value in crop[128, 128]) == (15, 80, 220)

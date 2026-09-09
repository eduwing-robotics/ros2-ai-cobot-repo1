#!/usr/bin/env python3
"""Shared registered-board crops for non-VRM presence classifiers."""

from __future__ import annotations

import cv2
import numpy as np


PRESENCE_CROP_SIZE = (256, 256)
PRESENCE_CROP_PIPELINE = (
    "registered_board_getRectSubPix_component_margin_square256_v1"
)
PRESENCE_MARGIN_BY_KEY = {
    "gpu": 0.16,
    "hbm": 0.20,
    "power_module": 0.14,
    "inductor": 0.28,
    "smd_capacitor": 0.30,
}


def crop_component_presence_slot(
    registered_board_bgr: np.ndarray,
    geometry: tuple[float, float, float, float],
    component_key: str,
) -> np.ndarray:
    """Return the exact crop that training and runtime must share."""

    if registered_board_bgr is None or registered_board_bgr.size == 0:
        raise ValueError("Registered board image is empty")
    if component_key not in PRESENCE_MARGIN_BY_KEY:
        raise ValueError(f"Unsupported presence component: {component_key}")
    margin_ratio = PRESENCE_MARGIN_BY_KEY[component_key]
    center_x, center_y, size_x, size_y = geometry
    width = max(24, int(round(size_x * (1.0 + 2.0 * margin_ratio))))
    height = max(24, int(round(size_y * (1.0 + 2.0 * margin_ratio))))
    crop = cv2.getRectSubPix(
        registered_board_bgr,
        (width, height),
        (float(center_x), float(center_y)),
    )
    return cv2.resize(crop, PRESENCE_CROP_SIZE, interpolation=cv2.INTER_CUBIC)

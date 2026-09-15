#!/usr/bin/env python3
"""Shared input contract for the S22 fixed-slot VRM state classifier."""

from __future__ import annotations

import cv2
import numpy as np


VRM_STATE_CROP_SIZE = (256, 256)
VRM_STATE_MARGIN_RATIO = 0.24
VRM_STATE_CROP_PIPELINE = "registered_board_getRectSubPix_margin0.24_square256_v2"


def crop_vrm_state_slot(
    registered_board_bgr: np.ndarray,
    geometry: tuple[float, float, float, float],
    margin_ratio: float = VRM_STATE_MARGIN_RATIO,
) -> np.ndarray:
    """Crop one VRM slot from the globally registered board.

    Dataset creation and runtime inference must both call this exact function;
    otherwise sub-pixel centring and aspect-ratio differences can change the
    classifier confidence even when the physical scene did not move.
    """

    if registered_board_bgr is None or registered_board_bgr.size == 0:
        raise ValueError("Registered board image is empty")
    center_x, center_y, size_x, size_y = geometry
    width = max(24, int(round(size_x * (1.0 + 2.0 * margin_ratio))))
    height = max(24, int(round(size_y * (1.0 + 2.0 * margin_ratio))))
    crop = cv2.getRectSubPix(
        registered_board_bgr,
        (width, height),
        (float(center_x), float(center_y)),
    )
    return cv2.resize(crop, VRM_STATE_CROP_SIZE, interpolation=cv2.INTER_CUBIC)

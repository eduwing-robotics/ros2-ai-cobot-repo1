#!/usr/bin/env python3
"""Shared image contract for the S22 VRM seating classifier.

Seating is intentionally separate from EMPTY/CORRECT/ROTATED.  A component can
be present and have the correct in-plane direction while one edge is resting on
the socket lip.  Dataset creation and runtime inference must use this exact
crop function so registration or interpolation differences do not become a
shortcut for the classifier.
"""

from __future__ import annotations

import numpy as np

from vrm_state_common import (
    VRM_STATE_CROP_PIPELINE,
    VRM_STATE_CROP_SIZE,
    VRM_STATE_MARGIN_RATIO,
    crop_vrm_state_slot,
)


VRM_SEATING_CROP_SIZE = VRM_STATE_CROP_SIZE
VRM_SEATING_MARGIN_RATIO = VRM_STATE_MARGIN_RATIO
VRM_SEATING_CROP_PIPELINE = VRM_STATE_CROP_PIPELINE


def crop_vrm_seating_slot(
    registered_board_bgr: np.ndarray,
    geometry: tuple[float, float, float, float],
) -> np.ndarray:
    """Return the fixed-slot colour crop used by seating train and runtime."""

    return crop_vrm_state_slot(
        registered_board_bgr,
        geometry,
        margin_ratio=VRM_SEATING_MARGIN_RATIO,
    )


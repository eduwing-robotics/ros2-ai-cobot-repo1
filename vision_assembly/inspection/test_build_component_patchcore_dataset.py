from pathlib import Path
import sys

import cv2
import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from build_component_patchcore_dataset import _crop_slot  # noqa: E402


def test_vertical_slot_is_normalized_to_horizontal_output():
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.rectangle(image, (90, 40), (110, 160), (255, 255, 255), -1)
    crop, rotated, source_size = _crop_slot(
        image, (100.0, 100.0, 20.0, 120.0), 0.1, (240, 80)
    )
    assert rotated is True
    assert source_size == (24, 144)
    assert crop.shape == (80, 240, 3)


def test_horizontal_slot_keeps_orientation():
    image = np.zeros((160, 240, 3), dtype=np.uint8)
    crop, rotated, source_size = _crop_slot(
        image, (120.0, 80.0, 120.0, 20.0), 0.1, (240, 80)
    )
    assert rotated is False
    assert source_size == (144, 24)
    assert crop.shape == (80, 240, 3)

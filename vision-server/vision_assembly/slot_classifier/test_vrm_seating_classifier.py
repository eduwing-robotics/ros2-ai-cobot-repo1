#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from build_vrm_seating_dataset import validate_spec  # noqa: E402
from train_vrm_seating_classifier import band_prediction, threshold_band  # noqa: E402
from vrm_seating_common import (  # noqa: E402
    VRM_SEATING_CROP_PIPELINE,
    VRM_SEATING_CROP_SIZE,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]


def test_locked_ground_truth_has_no_physical_scene_leakage() -> None:
    path = PROJECT_DIR / "vision_assembly/config/vrm_seating_ground_truth_v1.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    validate_spec(spec)
    split_by_physical = {}
    for scene in spec["registered_scenes"]:
        split_by_physical.setdefault(scene["physical_scene_id"], set()).add(scene["split"])
    assert all(len(splits) == 1 for splits in split_by_physical.values())
    holdout = [scene for scene in spec["registered_scenes"] if scene["split"] == "holdout"]
    assert any(scene["labels"]["vrm_05"] == "SEATING" for scene in holdout)


def test_seating_crop_contract_matches_runtime_state_crop() -> None:
    assert VRM_SEATING_CROP_PIPELINE == (
        "registered_board_getRectSubPix_margin0.24_square256_v2"
    )
    assert VRM_SEATING_CROP_SIZE == (256, 256)


def test_validation_band_keeps_an_unknown_gap() -> None:
    rows = [
        {"label": "flat", "seating_probability": 0.08},
        {"label": "flat", "seating_probability": 0.12},
        {"label": "seating", "seating_probability": 0.84},
        {"label": "seating", "seating_probability": 0.91},
    ]
    thresholds = threshold_band(
        [row for row in rows if row["label"] == "flat"],
        [row for row in rows if row["label"] == "seating"],
    )
    assert thresholds["validation_separated"] is True
    assert band_prediction(0.10, thresholds) == "FLAT"
    assert band_prediction(0.15, thresholds) == "UNKNOWN"
    assert band_prediction(0.90, thresholds) == "SEATING"


def test_overlapping_validation_never_invents_separation() -> None:
    rows = [
        {"label": "flat", "seating_probability": 0.55},
        {"label": "seating", "seating_probability": 0.45},
    ]
    thresholds = threshold_band(
        [row for row in rows if row["label"] == "flat"],
        [row for row in rows if row["label"] == "seating"],
    )
    assert thresholds["validation_separated"] is False
    assert band_prediction(0.50, thresholds) == "UNKNOWN"


def test_ground_truth_rejects_holdout_leakage() -> None:
    base = {
        "task": "vrm_fixed_slot_seating",
        "crop_pipeline": VRM_SEATING_CROP_PIPELINE,
        "registered_scenes": [],
    }
    labels = {slot: "FLAT" for slot in sorted({f"vrm_{i:02d}" for i in range(1, 6)})}
    labels["vrm_05"] = "SEATING"
    base["registered_scenes"] = [
        {
            "scene_id": "train",
            "physical_scene_id": "same",
            "split": "train",
            "labels": labels,
        },
        {
            "scene_id": "holdout",
            "physical_scene_id": "same",
            "split": "holdout",
            "labels": labels,
        },
    ]
    with pytest.raises(ValueError, match="leakage"):
        validate_spec(base)

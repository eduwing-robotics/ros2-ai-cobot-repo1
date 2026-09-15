#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys

import pytest


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from train_vrm_state_classifier import (  # noqa: E402
    checkpoint_is_better,
    class_scene_counts,
    split_scenes,
)


def _rows(scene_count: int):
    rows = []
    for index in range(scene_count):
        scene = f"scene_{index:02d}"
        for label in ("empty", "correct", "rotated"):
            rows.append({"scene_id": scene, "label": label, "crop_image": "unused.png"})
    return rows


def test_scene_split_has_no_leakage_and_all_classes() -> None:
    rows = _rows(8)
    train, validation, train_scenes, validation_scenes = split_scenes(rows, 0.25, 42)
    assert train_scenes.isdisjoint(validation_scenes)
    assert {row["label"] for row in train} == {"empty", "correct", "rotated"}
    assert {row["label"] for row in validation} == {"empty", "correct", "rotated"}


def test_scene_split_rejects_too_few_scenes() -> None:
    with pytest.raises(RuntimeError, match="At least four"):
        split_scenes(_rows(3), 0.25, 42)


def test_class_scene_counts_counts_unique_scenes() -> None:
    counts = class_scene_counts(_rows(5))
    assert counts == {"empty": 5, "correct": 5, "rotated": 5}


def test_checkpoint_tie_uses_lower_validation_loss() -> None:
    assert checkpoint_is_better(1.0, 0.2, 1.0, 0.4)
    assert not checkpoint_is_better(1.0, 0.5, 1.0, 0.4)


def test_candidate_flags_preserve_fixed_confidence(monkeypatch):
    import sys
    from train_vrm_state_classifier import parse_args
    monkeypatch.setattr(sys, 'argv', ['train', '--geometry-safe', '--fixed-minimum-confidence', '0.9'])
    args=parse_args()
    assert args.geometry_safe and args.fixed_minimum_confidence==.9


def test_invalid_confidence_rejected_before_training(monkeypatch):
    import sys
    import pytest
    from train_vrm_state_classifier import parse_args
    monkeypatch.setattr(sys, 'argv', ['train', '--fixed-minimum-confidence', 'nan'])
    with pytest.raises(SystemExit):
        parse_args()

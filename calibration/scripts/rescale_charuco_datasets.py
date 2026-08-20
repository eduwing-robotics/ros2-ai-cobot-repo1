#!/usr/bin/env python3
"""Uniformly rescale saved ChArUco translations after a physical board remeasurement."""

import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OLD_SQUARE_M = 0.025
NEW_SQUARE_M = 0.0251714286
NEW_MARKER_M = 0.0125857143
SCALE = NEW_SQUARE_M / OLD_SQUARE_M


def update(path, backup_dir):
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    target = payload.get("target", {})
    current = float(target.get("square_length_m", OLD_SQUARE_M))
    if abs(current - NEW_SQUARE_M) < 1e-10:
        print(f"Already scaled: {path}")
        return
    if abs(current - OLD_SQUARE_M) > 1e-10:
        raise SystemExit(f"Unexpected square length {current} in {path}; refusing to rescale")
    shutil.copy2(path, backup_dir / path.name)
    for sample in payload["samples"]:
        translation = sample["target_to_camera"]["translation_m"]
        sample["target_to_camera"]["translation_m"] = [float(v) * SCALE for v in translation]
    target["square_length_m"] = NEW_SQUARE_M
    target["marker_length_m"] = NEW_MARKER_M
    target["measurement_note"] = "Measured grid: 176 mm / 7 and 126 mm / 5; uniform mean used"
    payload["target"] = target
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Scaled {len(payload['samples'])} samples by {SCALE:.9f}: {path}")


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "archive" / f"before_board_scale_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    update(DATA_DIR / "handeye_samples.json", backup_dir)
    update(DATA_DIR / "validation_samples.json", backup_dir)
    result = DATA_DIR / "handeye_result.json"
    if result.exists():
        shutil.copy2(result, backup_dir / result.name)
    print(f"Backup: {backup_dir}")


if __name__ == "__main__":
    main()

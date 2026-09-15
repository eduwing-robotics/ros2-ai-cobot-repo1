#!/usr/bin/env python3
"""Derive fixed visualization baselines from held-out normal component crops."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from predict_component_patchcore import (
    DEFAULT_MODELS, DIR_TYPES, _checkpoint, _predict_outputs,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = (
    PROJECT_DIR / "vision_assembly/inspection/datasets/pcb_components_smd_v3"
)
DEFAULT_OUTPUT = (
    PROJECT_DIR / "runtime/inspection/patchcore/pcb_components_smd_v3"
    / "normal_calibration.json"
)


def percentiles(values: np.ndarray, points: tuple[float, ...]) -> dict[str, float]:
    return {
        str(point): float(np.percentile(values, point)) for point in points
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--models", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--component", choices=("all",) + tuple(sorted(DIR_TYPES)), default="all")
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; calibration requires the GPU")
    torch.set_float32_matmul_precision("high")

    dataset = args.dataset.expanduser().resolve()
    models = args.models.expanduser().resolve()
    output = args.output.expanduser().resolve()
    scratch = output.parent / "normal_calibration_runs"
    if output.is_file() and args.component != "all":
        existing = json.loads(output.read_text(encoding="utf-8"))
        components = dict(existing.get("components", {}))
    else:
        components = {}
    selected = sorted(DIR_TYPES) if args.component == "all" else (args.component,)
    for component in selected:
        source = dataset / component / "test/good"
        predictions = _predict_outputs(
            component, source, _checkpoint(models, component), scratch / component
        )
        scores = np.asarray(
            [float(item["score"]) for item in predictions.values()], dtype=np.float32
        )
        maps = [
            np.asarray(item["anomaly_map"], dtype=np.float32).ravel()
            for item in predictions.values() if item["anomaly_map"] is not None
        ]
        if not len(scores) or not maps:
            raise RuntimeError(f"No normal calibration output for {component}")
        pixels = np.concatenate(maps)
        components[component] = {
            "normal_count": int(len(scores)),
            "score": {
                "min": float(scores.min()), "max": float(scores.max()),
                "percentiles": percentiles(scores, (50.0, 90.0, 95.0, 99.0)),
            },
            "pixel": {
                "min": float(pixels.min()), "max": float(pixels.max()),
                "percentiles": percentiles(
                    pixels, (50.0, 90.0, 95.0, 99.0, 99.5, 99.9, 99.99)
                ),
            },
        }
        print(f"CALIBRATED {component}: {len(scores)} normal crops", flush=True)
    payload = {
        "schema_version": 1,
        "policy": "held_out_normal_fixed_visualization_baseline",
        "dataset": str(dataset),
        "models": str(models),
        "components": components,
        "warning": (
            "Normal calibration suppresses expected heatmap response only. "
            "Controlled defects are still required for PASS/FAIL thresholds."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"COMPONENT_PATCHCORE_CALIBRATION={output}")


if __name__ == "__main__":
    main()

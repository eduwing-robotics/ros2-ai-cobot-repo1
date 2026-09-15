#!/usr/bin/env python3
"""Run the baseline PCB PatchCore model on one rectified S22 board ROI."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import torch

from train_pcb_patchcore import save_prediction_visualizations


def triage(score: float, pass_max: float, anomaly_min: float) -> str:
    if not 0.0 <= pass_max < anomaly_min <= 1.0:
        raise ValueError("Expected 0 <= pass_max < anomaly_min <= 1")
    if score <= pass_max:
        return "NORMAL_CANDIDATE"
    if score >= anomaly_min:
        return "ANOMALY_CANDIDATE"
    return "RECHECK"


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image",
        type=Path,
        default=root / "runtime/inspection/s22_inspection_roi_latest.png",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=(
            root
            / "runtime/inspection/patchcore/pcb_whole_smd_v4"
            / "Patchcore/pcb_whole_smd_v4/v0/weights/lightning/model.ckpt"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "runtime/inspection/patchcore/whole_live_v4",
    )
    parser.add_argument("--image-height", type=int, default=768)
    parser.add_argument("--image-width", type=int, default=960)
    parser.add_argument(
        "--tuning-config", type=Path,
        default=root / "vision_assembly/config/whole_board_patchcore_v4.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image = args.image.resolve()
    checkpoint = args.checkpoint.resolve()
    output = args.output.resolve()
    tuning = json.loads(args.tuning_config.resolve().read_text(encoding="utf-8"))
    pass_max = float(tuning["decision"]["pass_candidate_max"])
    anomaly_min = float(tuning["decision"]["anomaly_candidate_min"])
    heatmap_visible_min = float(tuning["visualization"]["heatmap_visible_min"])
    if not image.is_file():
        raise FileNotFoundError(f"Inspection ROI does not exist: {image}")
    if not checkpoint.is_file():
        raise FileNotFoundError(f"PatchCore checkpoint does not exist: {checkpoint}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; run this on the RTX GPU host")
    output.mkdir(parents=True, exist_ok=True)
    torch.set_float32_matmul_precision("high")

    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    model = Patchcore(
        backbone="wide_resnet50_2",
        layers=("layer2", "layer3"),
        pre_trained=True,
        coreset_sampling_ratio=0.1,
        num_neighbors=9,
        pre_processor=Patchcore.configure_pre_processor(
            image_size=(args.image_height, args.image_width)
        ),
        visualizer=False,
    )
    engine = Engine(
        accelerator="gpu",
        devices=1,
        default_root_dir=output,
        logger=False,
        enable_model_summary=False,
    )
    predictions = engine.predict(
        model=model,
        ckpt_path=checkpoint,
        data_path=image,
        return_predictions=True,
    )
    count = save_prediction_visualizations(
        predictions, output, heatmap_visible_min=heatmap_visible_min
    )
    if count != 1:
        raise RuntimeError(f"Expected one prediction, received {count}")

    score_path = output / "prediction_scores.csv"
    with score_path.open(newline="", encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    visualization = output / row["visualization"]
    score = float(row["anomaly_score"])
    decision = triage(score, pass_max, anomaly_min)
    panel = cv2.imread(str(visualization), cv2.IMREAD_COLOR)
    if panel is None:
        raise RuntimeError(f"Cannot reopen PatchCore visualization: {visualization}")
    third = panel.shape[1] // 3
    cv2.rectangle(panel, (2 * third, 0), (panel.shape[1] - 1, 72), (18, 18, 18), -1)
    cv2.putText(
        panel,
        f"{decision} | score={score:.4f} | PROVISIONAL",
        (2 * third + 22, 49), cv2.FONT_HERSHEY_SIMPLEX,
        1.05, (80, 220, 255), 3, cv2.LINE_AA,
    )
    if not cv2.imwrite(str(visualization), panel, [cv2.IMWRITE_JPEG_QUALITY, 93]):
        raise RuntimeError(f"Cannot update PatchCore visualization: {visualization}")
    latest_visualization = output / "whole_patchcore_latest.png"
    latest_visualization.unlink(missing_ok=True)
    latest_visualization.symlink_to(visualization.resolve())
    report = {
        "schema_version": 1,
        "status": "UNVERIFIED_BASELINE_ONLY",
        "input_image": str(image),
        "model_predicted_label": row["predicted_label"],
        "anomaly_score": score,
        "decision": decision,
        "thresholds": {
            "normal_candidate_max": pass_max,
            "anomaly_candidate_min": anomaly_min,
            "heatmap_visible_min": heatmap_visible_min
        },
        "visualization": str(visualization),
        "limitation": (
            "The whole-board threshold is not production validated; combine this "
            "result with component-level and explicit presence/orientation checks."
        ),
    }
    report_path = output / "whole_patchcore_latest.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"PATCHCORE_LABEL={row['predicted_label']}")
    print(f"PATCHCORE_SCORE={row['anomaly_score']}")
    print(f"PATCHCORE_VISUALIZATION={visualization}")
    print(f"PATCHCORE_REPORT={report_path}")
    print("PATCHCORE_BASELINE_ONLY=1")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Train and evaluate the first S22 whole-board PatchCore baseline."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import torch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("vision_assembly/inspection/datasets/pcb_anomaly_v1"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runtime/inspection/patchcore/pcb_anomaly_v1"),
    )
    parser.add_argument("--image-height", type=int, default=512)
    parser.add_argument("--image-width", type=int, default=640)
    parser.add_argument("--coreset-ratio", type=float, default=0.1)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--run-name", default="pcb_anomaly_v1")
    return parser.parse_args()


def json_safe(value):
    if isinstance(value, torch.Tensor):
        if value.numel() == 1:
            return value.detach().cpu().item()
        return value.detach().cpu().tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def _items(value, count: int):
    if isinstance(value, torch.Tensor):
        return [value[index] for index in range(count)]
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value] * count


def fixed_anomaly_u8(
    anomaly_np: np.ndarray, visible_min: float = 0.0
) -> np.ndarray:
    """Map Anomalib's fixed 0..1 anomaly scale to color without per-frame stretch."""
    anomaly_np = np.nan_to_num(
        np.asarray(anomaly_np, dtype=np.float32), nan=0.0, posinf=1.0, neginf=0.0
    )
    if not 0.0 <= visible_min < 1.0:
        raise ValueError("visible_min must be in [0, 1)")
    scaled = np.clip((anomaly_np - visible_min) / (1.0 - visible_min), 0.0, 1.0)
    return (scaled * 255.0).astype(np.uint8)


def save_prediction_visualizations(
    predictions, output: Path, heatmap_visible_min: float = 0.0
) -> int:
    """Save readable source/heatmap/overlay panels for every prediction."""
    visual_dir = output / "visualizations"
    visual_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    for batch in predictions or []:
        paths = getattr(batch, "image_path", None)
        if paths is None:
            paths = getattr(batch, "image_paths", None)
        if paths is None:
            raise RuntimeError("Prediction batch does not expose image_path")
        paths = list(paths) if isinstance(paths, (list, tuple)) else [paths]
        count = len(paths)
        scores = _items(getattr(batch, "pred_score", float("nan")), count)
        labels = _items(getattr(batch, "pred_label", -1), count)
        maps = _items(getattr(batch, "anomaly_map", None), count)

        for index, source_value in enumerate(paths):
            source = Path(str(source_value))
            image = cv2.imread(str(source), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"Cannot read prediction source: {source}")
            score = float(json_safe(scores[index]))
            label_value = int(json_safe(labels[index]))
            label = "ANOMALY" if label_value == 1 else "GOOD"

            anomaly = maps[index]
            if anomaly is None:
                anomaly_u8 = np.zeros(image.shape[:2], dtype=np.uint8)
            else:
                anomaly_np = np.asarray(json_safe(anomaly), dtype=np.float32).squeeze()
                anomaly_np = cv2.resize(
                    anomaly_np,
                    (image.shape[1], image.shape[0]),
                    interpolation=cv2.INTER_LINEAR,
                )
                anomaly_u8 = fixed_anomaly_u8(anomaly_np, heatmap_visible_min)

            heatmap = cv2.applyColorMap(anomaly_u8, cv2.COLORMAP_TURBO)
            overlay = image.copy()
            blended = cv2.addWeighted(image, 0.60, heatmap, 0.40, 0.0)
            visible = anomaly_u8 > 0
            overlay[visible] = blended[visible]
            color = (40, 40, 240) if label == "ANOMALY" else (40, 210, 40)
            cv2.rectangle(overlay, (0, 0), (overlay.shape[1] - 1, 72), (18, 18, 18), -1)
            cv2.putText(
                overlay,
                f"{label}  score={score:.4f}",
                (22, 49),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.25,
                color,
                3,
                cv2.LINE_AA,
            )
            panel = np.hstack((image, heatmap, overlay))
            group = source.parent.name
            destination_dir = visual_dir / group
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / f"{source.stem}_patchcore.jpg"
            if not cv2.imwrite(str(destination), panel, [cv2.IMWRITE_JPEG_QUALITY, 93]):
                raise RuntimeError(f"Failed to save visualization: {destination}")
            rows.append({
                "filename": source.name,
                "source_group": group,
                "predicted_label": label,
                "anomaly_score": f"{score:.8f}",
                "visualization": str(destination.relative_to(output)),
            })

    score_path = output / "prediction_scores.csv"
    with score_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("filename", "source_group", "predicted_label", "anomaly_score", "visualization"),
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    args = parse_args()
    torch.set_float32_matmul_precision("high")
    dataset = args.dataset.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    groups = ("train/good", "test/good", "test/mixed_defect")
    counts = {
        relative: len(list((dataset / relative).glob("*.png")))
        for relative in groups
    }
    if min(counts.values()) <= 0:
        raise RuntimeError(f"Incomplete whole-board dataset: {counts}")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; run this launcher on the RTX GPU host")

    from anomalib.data import Folder
    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    datamodule = Folder(
        name=args.run_name,
        root=dataset,
        normal_dir="train/good",
        normal_test_dir="test/good",
        abnormal_dir="test/mixed_defect",
        normal_split_ratio=0.0,
        train_batch_size=2,
        eval_batch_size=1,
        num_workers=args.num_workers,
        test_split_mode="from_dir",
        val_split_mode="from_test",
        val_split_ratio=0.4,
        seed=42,
    )
    pre_processor = Patchcore.configure_pre_processor(
        image_size=(args.image_height, args.image_width),
    )
    model = Patchcore(
        backbone="wide_resnet50_2",
        layers=("layer2", "layer3"),
        pre_trained=True,
        coreset_sampling_ratio=args.coreset_ratio,
        num_neighbors=9,
        pre_processor=pre_processor,
        visualizer=False,
    )
    engine = Engine(
        accelerator="gpu",
        devices=1,
        max_epochs=1,
        default_root_dir=output,
        logger=False,
        enable_model_summary=True,
    )

    engine.fit(model=model, datamodule=datamodule)
    metrics = engine.test(model=model, datamodule=datamodule)
    predictions = engine.predict(
        model=model,
        data_path=dataset / "test",
        return_predictions=True,
    )
    visualization_count = save_prediction_visualizations(predictions, output)

    summary = {
        "status": "baseline_only",
        "model": "PatchCore/wide_resnet50_2",
        "input_size": [args.image_height, args.image_width],
        "dataset_counts": counts,
        "validation_split_ratio_from_test": 0.4,
        "metrics": json_safe(metrics),
        "prediction_batches": len(predictions or []),
        "visualization_count": visualization_count,
        "limitations": [
            f"Only {counts['train/good']} normal training images are available.",
            "Defect images have only a generic mixed_defect label.",
            "Whole-board resizing is not sufficient to certify tiny white-pin defects.",
            "This baseline is not a production pass/fail model.",
        ],
    }
    result_path = output / "baseline_summary.json"
    result_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"PATCHCORE_RESULT={result_path}")


if __name__ == "__main__":
    main()

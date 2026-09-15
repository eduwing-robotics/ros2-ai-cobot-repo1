#!/usr/bin/env python3
"""Train the S22-only six-class YOLO instance-segmentation provider."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    project = Path(__file__).resolve().parents[2]
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        type=Path,
        default=root / "s22_parts_seg_dataset/s22_parts_seg.yaml",
    )
    parser.add_argument("--model", default="yolo26n-seg.pt")
    parser.add_argument("--epochs", type=int, default=150)
    parser.add_argument("--patience", type=int, default=35)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--batch", type=int, default=4)
    parser.add_argument("--device", default="0")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--name", default="s22_parts_seg")
    parser.add_argument("--project", type=Path, default=root / "runs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = args.data.resolve()
    if not data.is_file():
        raise FileNotFoundError(
            f"Segmentation dataset YAML does not exist: {data}. "
            "Run run_build_s22_segmentation_dataset.sh first."
        )
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; S22 segmentation training requires the RTX GPU")
    args.project.mkdir(parents=True, exist_ok=True)
    torch.set_float32_matmul_precision("high")
    model = YOLO(args.model)
    model.train(
        data=str(data),
        epochs=args.epochs,
        patience=args.patience,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        project=str(args.project.resolve()),
        name=args.name,
        seed=args.seed,
        deterministic=True,
        cache="disk",
        close_mosaic=0,
        mosaic=0.0,
        mixup=0.0,
        copy_paste=0.0,
        degrees=3.0,
        translate=0.04,
        scale=0.15,
        perspective=0.0005,
        fliplr=0.0,
        flipud=0.0,
        hsv_h=0.01,
        hsv_s=0.20,
        hsv_v=0.18,
        plots=True,
        exist_ok=False,
        resume=args.resume,
    )
    save_dir = Path(model.trainer.save_dir).resolve()
    summary = {
        "schema_version": 1,
        "status": "TRAINED_UNVERIFIED_PROVIDER",
        "camera": "S22 optical still",
        "data": str(data),
        "model": args.model,
        "input_size": args.imgsz,
        "epochs_requested": args.epochs,
        "save_dir": str(save_dir),
        "best_weights": str(save_dir / "weights/best.pt"),
        "authority": "ADVISORY_ONLY until controlled slot-level validation",
    }
    (save_dir / "s22_segmentation_training_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    candidate_dir = Path(__file__).resolve().parent / "models"
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_dir / "s22_parts_seg_candidate.pt"
    candidate.unlink(missing_ok=True)
    candidate.symlink_to((save_dir / "weights/best.pt").resolve())
    print(f"S22_SEG_RUN={save_dir}")
    print(f"S22_SEG_BEST={save_dir / 'weights/best.pt'}")
    print(f"S22_SEG_CANDIDATE={candidate}")
    print("S22_SEG_AUTHORITY=ADVISORY_ONLY")


if __name__ == "__main__":
    main()

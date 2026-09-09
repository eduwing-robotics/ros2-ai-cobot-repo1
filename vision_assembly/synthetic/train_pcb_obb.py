#!/usr/bin/env python3
"""Train the six-class PCB inspection OBB model on Unity-native images."""
import argparse
from pathlib import Path

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="yolo26n-obb.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="0")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    data = root / "unity_native_dataset" / "dataset.yaml"
    model = YOLO(args.model)
    model.train(
        data=str(data), epochs=args.epochs, imgsz=args.imgsz,
        batch=args.batch, device=args.device,
        project=str(root / "runs"), name="pcb_obb_unity",
        workers=4, cache=False,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Train the combined real-image semiconductor-part OBB detector."""
import argparse
from pathlib import Path

import yaml
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='yolo26n-obb.pt')
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--imgsz', type=int, default=960)
    parser.add_argument('--batch', type=int, default=8)
    parser.add_argument('--device', default='0')
    parser.add_argument('--name', default='parts_obb_6class')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    dataset = root/'multiclass_dataset'
    config = root/'multiclass_obb_runtime.yaml'
    config.write_text(yaml.safe_dump({
        'path': str(dataset), 'train': 'images/train', 'val': 'images/val',
        'names': {0: 'gpu', 1: 'hbm', 2: 'power_module', 3: 'vrm',
                  4: 'inductor', 5: 'smd_capacitor'},
    }, sort_keys=False), encoding='utf-8')
    model = YOLO(args.model)
    model.train(data=str(config), epochs=args.epochs, imgsz=args.imgsz,
                batch=args.batch, device=args.device, project=str(root/'runs'),
                name=args.name, workers=4, cache=True, exist_ok=True)


if __name__ == '__main__':
    main()

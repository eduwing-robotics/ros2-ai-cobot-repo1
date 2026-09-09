#!/usr/bin/env python3
"""Train the one-class GPU OBB model with a portable absolute runtime config."""
import argparse
from pathlib import Path

import yaml
from ultralytics import YOLO


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',default='yolo26n-obb.pt')
    parser.add_argument('--epochs',type=int,default=100)
    parser.add_argument('--imgsz',type=int,default=960)
    parser.add_argument('--batch',type=int,default=8)
    parser.add_argument('--device',default=None)
    args=parser.parse_args();root=Path(__file__).resolve().parent
    dataset=root/'dataset';runtime=root/'gpu_obb_runtime.yaml'
    runtime.write_text(yaml.safe_dump({
        'path':str(dataset),'train':'images/train','val':'images/val',
        'names':{0:'gpu'}},sort_keys=False),encoding='utf-8')
    model=YOLO(args.model)
    model.train(data=str(runtime),epochs=args.epochs,imgsz=args.imgsz,
                batch=args.batch,device=args.device,project=str(root/'runs'),
                name='gpu_obb')


if __name__=='__main__':main()

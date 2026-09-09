"""Offline confidence/checkpoint diagnostic; does not tune runtime thresholds."""
import hashlib
import json
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from build_vrm_fixed_crop_dataset import ROOT
from common import load_yolo_segments


def main():
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required')
    torch.set_num_threads(2)
    source = ROOT/'vision_assembly/segmentation/vrm_boundary_adaptation_v1'
    run = ROOT/'vision_assembly/segmentation/runs/vrm_fixed_boundary_adapted_v1'
    output = run/'checkpoint_failure_probe.json'
    if output.exists():
        raise FileExistsError(output)
    rows = []
    for checkpoint in ['best', 'last']:
        weights = run/f'weights/{checkpoint}.pt'
        model = YOLO(str(weights))
        for sample in json.loads((source/'partition.json').read_text())['rows']:
            path = source/'images'/f'{sample["stem"]}.png'
            if hashlib.sha256(path.read_bytes()).hexdigest() != sample['crop_sha256']:
                raise ValueError('Changed crop')
            image = cv2.imread(str(path))
            h, w = image.shape[:2]
            poly = load_yolo_segments(source/'reviewed_labels'/f'{sample["stem"]}.txt', w, h)[0][1]
            truth = np.zeros((h,w), np.uint8)
            cv2.fillPoly(truth, [np.int32(poly)], 1)
            result = model.predict(image, imgsz=320, device=0, conf=.001, retina_masks=True, verbose=False)[0]
            candidates = []
            if result.masks is not None:
                for polygon, confidence in zip(result.masks.xy, result.boxes.conf.cpu().tolist()):
                    mask = np.zeros_like(truth)
                    cv2.fillPoly(mask, [np.int32(polygon)], 1)
                    iou = float(np.logical_and(mask,truth).sum()/max(1,np.logical_or(mask,truth).sum()))
                    candidates.append(dict(confidence=confidence, iou=iou))
            rows.append(dict(checkpoint=checkpoint, weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
                             stem=sample['stem'], candidates=candidates))
    report = dict(role='TRAINING_FIT_DIAGNOSTIC_ONLY', runtime_enabled=False,
                  diagnostic_confidence=.001, unchanged_runtime_confidence=.25, rows=rows)
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

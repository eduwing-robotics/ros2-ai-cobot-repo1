#!/usr/bin/env python3
"""Train scene-split advisory PRESENT/EMPTY classifiers per component type."""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import random

from PIL import Image
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

from component_presence_common import PRESENCE_CROP_PIPELINE


PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT / "vision_assembly/slot_classifier/datasets/component_presence_v1"
DEFAULT_OUTPUT = PROJECT / "vision_assembly/slot_classifier/models/component_presence_candidate"
LABELS = ("EMPTY", "PRESENT")
LABEL_INDEX = {name.lower(): index for index, name in enumerate(LABELS)}
COMPONENTS = ("gpu", "hbm", "power_module", "inductor", "smd_capacitor")


class Rows(Dataset):
    def __init__(self, root: Path, rows: list[dict], transform):
        self.root, self.rows, self.transform = root, rows, transform

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        image = Image.open(self.root / row["crop_image"]).convert("RGB")
        return self.transform(image), LABEL_INDEX[row["label"]]


def load_manifest(root: Path) -> list[dict]:
    path = root / "manifest.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    for row in rows:
        if row["label"] not in LABEL_INDEX:
            raise RuntimeError(f"Invalid label: {row['label']}")
        if row["crop_pipeline"] != PRESENCE_CROP_PIPELINE:
            raise RuntimeError(f"Crop pipeline mismatch: {row['crop_pipeline']}")
        if row["illumination"] != "ambient":
            raise RuntimeError("Only ambient/flash-off data is allowed")
    return rows


def choose_split(rows: list[dict], fraction: float, seed: int):
    scenes = sorted({row["scene_id"] for row in rows})
    rng = random.Random(seed)
    rng.shuffle(scenes)
    target = max(4, round(len(scenes) * fraction))
    # Search deterministic shuffled windows until both labels occur in both sets.
    for offset in range(len(scenes)):
        validation = {scenes[(offset + i) % len(scenes)] for i in range(target)}
        train = set(scenes) - validation
        tr = [row for row in rows if row["scene_id"] in train]
        va = [row for row in rows if row["scene_id"] in validation]
        if {row["label"] for row in tr} == set(LABEL_INDEX) and {row["label"] for row in va} == set(LABEL_INDEX):
            return tr, va, sorted(train), sorted(validation)
    raise RuntimeError("No leakage-free scene split contains EMPTY and PRESENT")


def evaluate(model, loader, device):
    model.eval()
    logits_all, targets_all = [], []
    loss_sum = 0.0
    criterion = nn.CrossEntropyLoss()
    with torch.inference_mode():
        for images, targets in loader:
            images, targets = images.to(device), targets.to(device)
            logits = model(images)
            loss_sum += float(criterion(logits, targets).item()) * len(targets)
            logits_all.append(logits.cpu())
            targets_all.append(targets.cpu())
    logits, targets = torch.cat(logits_all), torch.cat(targets_all)
    probs = logits.softmax(1)
    pred = probs.argmax(1)
    recalls = {}
    for idx, label in enumerate(LABELS):
        mask = targets == idx
        recalls[label] = float((pred[mask] == idx).float().mean())
    true_probs = probs.gather(1, targets[:, None]).squeeze(1)
    return {
        "loss": loss_sum / len(targets),
        "accuracy": float((pred == targets).float().mean()),
        "macro_recall": sum(recalls.values()) / 2,
        "per_class_recall": recalls,
        "minimum_true_class_probability": float(true_probs.min()),
        "mean_true_class_probability": float(true_probs.mean()),
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--validation-fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=47)
    parser.add_argument("--component", choices=COMPONENTS)
    return parser.parse_args()


def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    root, output = args.dataset.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    all_rows = load_manifest(root)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    normalize = transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))
    train_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomAffine(3, translate=(0.02, 0.02), scale=(0.97, 1.03)),
        transforms.ColorJitter(brightness=0.06, contrast=0.06, saturation=0.03),
        transforms.ToTensor(), normalize,
    ])
    eval_tf = transforms.Compose([transforms.Resize((224, 224)), transforms.ToTensor(), normalize])
    summary_path = output / "summary.json"
    summary = (
        json.loads(summary_path.read_text(encoding="utf-8"))
        if args.component and summary_path.is_file()
        else {}
    )
    selected_components = (args.component,) if args.component else COMPONENTS
    for component in selected_components:
        rows = [row for row in all_rows if row["component_key"] == component]
        train_rows, val_rows, train_scenes, val_scenes = choose_split(
            rows, args.validation_fraction, args.seed + COMPONENTS.index(component)
        )
        counts = Counter(row["label"] for row in train_rows)
        weights = torch.tensor([len(train_rows) / (2 * counts[label.lower()]) for label in LABELS], device=device)
        train_loader = DataLoader(Rows(root, train_rows, train_tf), batch_size=args.batch_size, shuffle=True)
        val_loader = DataLoader(Rows(root, val_rows, eval_tf), batch_size=args.batch_size, shuffle=False)
        model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, 2)
        model.to(device)
        criterion = nn.CrossEntropyLoss(weight=weights)
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
        best, best_state = None, None
        for epoch in range(1, args.epochs + 1):
            model.train()
            for images, targets in train_loader:
                images, targets = images.to(device), targets.to(device)
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(model(images), targets)
                loss.backward()
                optimizer.step()
            metrics = evaluate(model, val_loader, device)
            if best is None or metrics["macro_recall"] > best["macro_recall"] or (
                metrics["macro_recall"] == best["macro_recall"] and metrics["loss"] < best["loss"]
            ):
                best, best_state = metrics, copy.deepcopy(model.state_dict())
            print(f"{component} epoch={epoch:02d} recall={metrics['macro_recall']:.4f} loss={metrics['loss']:.4f}")
        model.load_state_dict(best_state)
        model.cpu().eval()
        example = torch.zeros(1, 3, 224, 224)
        model_path = output / f"{component}_presence.torchscript.pt"
        torch.jit.trace(model, example).save(str(model_path))
        metadata = {
            "schema_version": 1,
            "task": "fixed_slot_component_presence",
            "component_key": component,
            "classes": list(LABELS),
            "crop_pipeline": PRESENCE_CROP_PIPELINE,
            "input_size": 224,
            "normalization": "ImageNet",
            "authority": "ADVISORY_ONLY",
            "validated": False,
            "train_scenes": train_scenes,
            "validation_scenes": val_scenes,
            "train_counts": dict(Counter(row["label"] for row in train_rows)),
            "validation_counts": dict(Counter(row["label"] for row in val_rows)),
            "validation_metrics": best,
            "robot_command_sent": False,
            "conveyor_command_sent": False,
        }
        (output / f"{component}_presence.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        summary[component] = metadata
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"OUTPUT={output}")
    print(f"DEVICE={device}")
    print("AUTHORITY=ADVISORY_ONLY")


if __name__ == "__main__":
    main()

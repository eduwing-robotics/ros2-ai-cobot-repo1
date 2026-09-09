#!/usr/bin/env python3
"""Train an advisory S22 fixed-slot VRM state classifier.

Physical scene IDs, not individual crops, are split between train and
validation. Use --geometry-safe for small-angle labels: it disables legacy
affine augmentation. Horizontal/vertical flips are never applied.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path
import random
from typing import Any

from PIL import Image
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms

from vrm_state_common import VRM_STATE_CROP_PIPELINE


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_DIR / "vision_assembly/slot_classifier/datasets/vrm_state_v2"
DEFAULT_MODELS = PROJECT_DIR / "vision_assembly/slot_classifier/models"
CLASS_ORDER = ("EMPTY", "CORRECT", "ROTATED")
LABEL_INDEX = {label.lower(): index for index, label in enumerate(CLASS_ORDER)}


class ManifestDataset(Dataset):
    def __init__(self, root: Path, rows: list[dict[str, Any]], transform):
        self.root = root
        self.rows = rows
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        image = Image.open(self.root / row["crop_image"]).convert("RGB")
        return self.transform(image), LABEL_INDEX[row["label"]]


def load_rows(dataset: Path) -> list[dict[str, Any]]:
    manifest = dataset / "manifest.jsonl"
    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line]
    invalid = sorted({row.get("label") for row in rows} - set(LABEL_INDEX))
    if invalid:
        raise RuntimeError(f"Unexpected VRM state labels: {invalid}")
    if any(row.get("illumination") != "ambient" for row in rows):
        raise RuntimeError("VRM production classifier accepts ambient captures only")
    return rows


def split_scenes(
    rows: list[dict[str, Any]], validation_fraction: float, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str], set[str]]:
    scenes = sorted({str(row["scene_id"]) for row in rows})
    if len(scenes) < 4:
        raise RuntimeError("At least four independent physical scenes are required")
    labels_by_scene = {
        scene: {row["label"] for row in rows if str(row["scene_id"]) == scene}
        for scene in scenes
    }
    validation_count = max(1, min(len(scenes) - 1, round(len(scenes) * validation_fraction)))
    rng = random.Random(seed)
    choices = list(combinations(scenes, validation_count))
    rng.shuffle(choices)
    required = set(LABEL_INDEX)
    selected = None
    for candidate in choices:
        validation_scenes = set(candidate)
        train_scenes = set(scenes) - validation_scenes
        validation_labels = set().union(*(labels_by_scene[item] for item in validation_scenes))
        train_labels = set().union(*(labels_by_scene[item] for item in train_scenes))
        if validation_labels == required and train_labels == required:
            selected = (train_scenes, validation_scenes)
            break
    if selected is None:
        raise RuntimeError("No leakage-free scene split contains all three labels in both partitions")
    train_scenes, validation_scenes = selected
    train_rows = [row for row in rows if str(row["scene_id"]) in train_scenes]
    validation_rows = [row for row in rows if str(row["scene_id"]) in validation_scenes]
    return train_rows, validation_rows, train_scenes, validation_scenes


def class_scene_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    scenes: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        scenes[row["label"]].add(str(row["scene_id"]))
    return {label: len(scenes[label]) for label in LABEL_INDEX}


def metrics(logits: torch.Tensor, targets: torch.Tensor) -> tuple[float, list[float]]:
    predictions = logits.argmax(dim=1)
    recalls = []
    for class_index in range(len(CLASS_ORDER)):
        mask = targets == class_index
        recalls.append(
            float((predictions[mask] == class_index).float().mean().item())
            if bool(mask.any())
            else 0.0
        )
    return sum(recalls) / len(recalls), recalls


def checkpoint_is_better(
    macro_recall: float,
    validation_loss: float,
    best_macro_recall: float,
    best_validation_loss: float,
) -> bool:
    """Prefer recall, then the later/more confident lower-loss checkpoint."""

    return macro_recall > best_macro_recall + 1e-9 or (
        abs(macro_recall - best_macro_recall) <= 1e-9
        and validation_loss < best_validation_loss
    )


def deterministic_evaluation(
    model: nn.Module,
    dataset: Path,
    rows: list[dict[str, Any]],
    transform,
) -> dict[str, Any]:
    loader = DataLoader(
        ManifestDataset(dataset, rows, transform),
        batch_size=max(1, min(64, len(rows))),
        shuffle=False,
        num_workers=0,
    )
    all_logits, all_targets = [], []
    with torch.inference_mode():
        for images, targets in loader:
            all_logits.append(model(images))
            all_targets.append(targets)
    logits = torch.cat(all_logits)
    targets = torch.cat(all_targets)
    probabilities = torch.softmax(logits, dim=1)
    predictions = probabilities.argmax(dim=1)
    macro_recall, recalls = metrics(logits, targets)
    true_probabilities = probabilities.gather(1, targets[:, None]).squeeze(1)
    return {
        "accuracy": float((predictions == targets).float().mean().item()),
        "macro_recall": macro_recall,
        "per_class_recall": dict(zip(CLASS_ORDER, recalls)),
        "minimum_true_class_probability": float(true_probabilities.min().item()),
        "mean_true_class_probability": float(true_probabilities.mean().item()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--epochs", type=int, default=35)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--input-size", type=int, default=224)
    parser.add_argument("--minimum-scenes-per-class", type=int, default=4)
    parser.add_argument("--validation-fraction", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--geometry-safe", action="store_true", help="Disable pose-changing augmentation")
    parser.add_argument("--fixed-minimum-confidence", type=float)
    parser.add_argument("--init-model", type=Path, help="Initialize from local TorchScript; no weight download")
    args = parser.parse_args()
    if args.fixed_minimum_confidence is not None and not 0 < args.fixed_minimum_confidence <= 1:
        parser.error('--fixed-minimum-confidence must be finite and in (0,1]')
    return args


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    dataset = args.dataset.expanduser().resolve()
    rows = load_rows(dataset)
    scene_counts = class_scene_counts(rows)
    short = {
        label: count
        for label, count in scene_counts.items()
        if count < args.minimum_scenes_per_class
    }
    if short:
        raise RuntimeError(
            f"Insufficient independent scenes per class: {short}; "
            f"minimum={args.minimum_scenes_per_class}"
        )
    train_rows, validation_rows, train_scenes, validation_scenes = split_scenes(
        rows, args.validation_fraction, args.seed
    )
    normalize = transforms.Normalize(
        mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
    )
    train_transform = transforms.Compose(
        [
            transforms.Resize((args.input_size, args.input_size)),
            transforms.RandomAffine(
                degrees=4.0, translate=(0.025, 0.025), scale=(0.96, 1.04)
            ),
            transforms.ColorJitter(brightness=0.08, contrast=0.08, saturation=0.04),
            transforms.ToTensor(),
            normalize,
        ]
    )
    if args.geometry_safe:
        train_transform.transforms = [t for t in train_transform.transforms
                                      if not isinstance(t, transforms.RandomAffine)]
    validation_transform = transforms.Compose(
        [
            transforms.Resize((args.input_size, args.input_size)),
            transforms.ToTensor(),
            normalize,
        ]
    )
    train_dataset = ManifestDataset(dataset, train_rows, train_transform)
    validation_dataset = ManifestDataset(dataset, validation_rows, validation_transform)
    train_counts = Counter(row["label"] for row in train_rows)
    weights = torch.tensor(
        [len(train_rows) / (len(CLASS_ORDER) * train_counts[label.lower()]) for label in CLASS_ORDER],
        dtype=torch.float32,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = models.efficientnet_b0(weights=None if args.init_model else models.EfficientNet_B0_Weights.IMAGENET1K_V1)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(CLASS_ORDER))
    if args.init_model:
        model.load_state_dict(torch.jit.load(str(args.init_model), map_location='cpu').state_dict())
    model.to(device)
    criterion = nn.CrossEntropyLoss(weight=weights.to(device))
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda"
    )
    validation_loader = DataLoader(
        validation_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda"
    )
    best_macro_recall = -1.0
    best_validation_loss = float("inf")
    best_state = None
    best_recalls: list[float] = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), targets)
            loss.backward()
            optimizer.step()
        model.eval()
        all_logits, all_targets = [], []
        validation_loss_sum = 0.0
        validation_samples = 0
        with torch.inference_mode():
            for images, targets in validation_loader:
                logits = model(images.to(device))
                validation_loss_sum += float(
                    criterion(logits, targets.to(device)).item()
                ) * len(targets)
                validation_samples += len(targets)
                all_logits.append(logits.cpu())
                all_targets.append(targets)
        macro_recall, recalls = metrics(torch.cat(all_logits), torch.cat(all_targets))
        validation_loss = validation_loss_sum / max(1, validation_samples)
        print(
            f"epoch={epoch:03d} macro_recall={macro_recall:.4f} "
            f"validation_loss={validation_loss:.6f} "
            + " ".join(
                f"{name.lower()}_recall={value:.4f}"
                for name, value in zip(CLASS_ORDER, recalls)
            )
        )
        if checkpoint_is_better(
            macro_recall,
            validation_loss,
            best_macro_recall,
            best_validation_loss,
        ):
            best_macro_recall = macro_recall
            best_validation_loss = validation_loss
            best_recalls = recalls
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
    if best_state is None:
        raise RuntimeError("Training produced no checkpoint")
    model.load_state_dict(best_state)
    model.eval().cpu()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    model_path = output / "vrm_state.torchscript.pt"
    scripted = torch.jit.trace(model, torch.zeros(1, 3, args.input_size, args.input_size))
    torch.jit.save(scripted, str(model_path))
    train_evaluation = deterministic_evaluation(
        scripted, dataset, train_rows, validation_transform
    )
    validation_evaluation = deterministic_evaluation(
        scripted, dataset, validation_rows, validation_transform
    )
    if validation_evaluation["accuracy"] == 1.0:
        minimum_confidence = max(
            0.50,
            min(
                0.80,
                validation_evaluation["minimum_true_class_probability"] - 0.03,
            ),
        )
    else:
        minimum_confidence = 0.80
    if args.fixed_minimum_confidence is not None:
        if not 0 < args.fixed_minimum_confidence <= 1:
            raise ValueError('Invalid fixed confidence')
        minimum_confidence = args.fixed_minimum_confidence
    metadata = {
        "schema_version": 2,
        "task": "vrm_fixed_slot_state",
        "class_order": list(CLASS_ORDER),
        "input_size": args.input_size,
        "crop_pipeline": VRM_STATE_CROP_PIPELINE,
        "minimum_confidence": minimum_confidence,
        "minimum_confidence_policy": (
            "fixed experimental threshold; authority unchanged" if args.fixed_minimum_confidence is not None else
            "advisory held-out minimum true-class probability minus 0.03, "
            "clamped to [0.50, 0.80]"
        ),
        "authority": "ADVISORY_ONLY",
        "validated": False,
        "geometry_safe_augmentation": args.geometry_safe,
        "initialization_model": str(args.init_model) if args.init_model else None,
        "validation_policy": "physical_scene_holdout",
        "train_scenes": sorted(train_scenes),
        "validation_scenes": sorted(validation_scenes),
        "scene_counts_per_class": scene_counts,
        "best_macro_recall": best_macro_recall,
        "best_validation_loss": best_validation_loss,
        "per_class_recall": dict(zip(CLASS_ORDER, best_recalls)),
        "deterministic_train_evaluation": train_evaluation,
        "deterministic_validation_evaluation": validation_evaluation,
        "restriction": "Cannot become AUTHORITATIVE without controlled physical defect validation.",
    }
    metadata_path = output / "vrm_state.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"VRM_STATE_MODEL={model_path}")
    print(f"VRM_STATE_METADATA={metadata_path}")
    print("MODEL_AUTHORITY=ADVISORY_ONLY")


if __name__ == "__main__":
    main()

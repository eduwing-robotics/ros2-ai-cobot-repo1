#!/usr/bin/env python3
"""Train and regression-evaluate the advisory S22 VRM seating classifier.

Thresholds and checkpoint selection use only the train/validation partitions.
The locked VRM05 lip scene is never used for training or threshold calculation.
It was consumed by the first candidate comparison and is therefore a fixed
regression set, not a fresh blind holdout.  A newly reseated physical scene is
required before this provider can be considered for authoritative promotion.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random
from typing import Any

from PIL import Image
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import models, transforms

from vrm_seating_common import VRM_SEATING_CROP_PIPELINE


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_DIR / "vision_assembly/slot_classifier/datasets/vrm_seating_v3"
DEFAULT_OUTPUT = PROJECT_DIR / "vision_assembly/slot_classifier/models/vrm_seating_candidate_v4"
CLASS_ORDER = ("FLAT", "SEATING")
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
        return self.transform(image), LABEL_INDEX[row["label"]], index


def load_rows(dataset: Path) -> list[dict[str, Any]]:
    manifest = dataset / "manifest.jsonl"
    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line
    ]
    invalid_labels = sorted({row.get("label") for row in rows} - set(LABEL_INDEX))
    invalid_splits = sorted(
        {row.get("split") for row in rows} - {"train", "validation", "holdout"}
    )
    if invalid_labels:
        raise RuntimeError(f"Unexpected seating labels: {invalid_labels}")
    if invalid_splits:
        raise RuntimeError(f"Unexpected seating splits: {invalid_splits}")
    if any(row.get("crop_pipeline") != VRM_SEATING_CROP_PIPELINE for row in rows):
        raise RuntimeError("Dataset/runtime seating crop pipeline mismatch")
    physical_splits: dict[str, set[str]] = {}
    for row in rows:
        physical_splits.setdefault(str(row["physical_scene_id"]), set()).add(
            str(row["split"])
        )
    leaked = {key: value for key, value in physical_splits.items() if len(value) != 1}
    if leaked:
        raise RuntimeError(f"Physical-scene leakage: {leaked}")
    train_labels = {row["label"] for row in rows if row["split"] == "train"}
    holdout_labels = {row["label"] for row in rows if row["split"] == "holdout"}
    validation_labels = {
        row["label"] for row in rows if row["split"] == "validation"
    }
    if train_labels != set(LABEL_INDEX) or holdout_labels != set(LABEL_INDEX):
        raise RuntimeError("Train and locked holdout must contain FLAT and SEATING")
    if validation_labels != {"flat"}:
        raise RuntimeError(
            "Validation is reserved for independent FLAT false-positive controls"
        )
    return rows


def threshold_band(
    validation_probabilities: list[dict[str, Any]],
    training_probabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a fail-safe band from independent FLAT and development SEATING.

    Both available development seating modes are needed for training, so the
    independent validation partition is deliberately all-flat.  Training
    seating probabilities can set only an advisory boundary.  The locked
    VRM05 scene never feeds back into this calculation.
    """

    flat = [
        float(row["seating_probability"])
        for row in validation_probabilities
        if row["label"] == "flat"
    ]
    seating = [
        float(row["seating_probability"])
        for row in training_probabilities
        if row["label"] == "seating"
    ]
    if not flat or not seating:
        raise ValueError("Independent FLAT and development SEATING rows are required")
    max_flat = max(flat)
    min_seating = min(seating)
    separated = max_flat < min_seating
    if separated:
        gap = min_seating - max_flat
        # A fail-safe classifier must not call the broad interval between a
        # normal control and a learned defect "FLAT".  Keep the observed
        # independent-normal maximum as the PASS edge.  Require an additional
        # 50% relative plus 0.02 absolute probability guard before SEATING;
        # everything between those limits is UNKNOWN.
        flat_max = max_flat
        seating_min = max_flat + max(0.02, 0.50 * max_flat)
        if seating_min >= min_seating:
            flat_max = min(0.10, min(flat))
            seating_min = max(0.90, max(seating))
            separated = False
    else:
        # No data-supported decision interval exists.  Keep only very strong
        # evidence and return UNKNOWN for the broad ambiguous region.
        flat_max = min(0.10, min(flat))
        seating_min = max(0.90, max(seating))
    return {
        "validation_separated": separated,
        "validation_max_flat_seating_probability": max_flat,
        "development_train_min_seating_probability": min_seating,
        "flat_max_seating_probability": float(flat_max),
        "seating_min_probability": float(seating_min),
    }


def band_prediction(probability: float, thresholds: dict[str, Any]) -> str:
    if probability >= float(thresholds["seating_min_probability"]):
        return "SEATING"
    if probability <= float(thresholds["flat_max_seating_probability"]):
        return "FLAT"
    return "UNKNOWN"


def evaluate(
    model: nn.Module,
    dataset: Path,
    rows: list[dict[str, Any]],
    transform,
    device: torch.device,
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    loader = DataLoader(
        ManifestDataset(dataset, rows, transform),
        batch_size=max(1, min(64, len(rows))),
        shuffle=False,
        num_workers=0,
    )
    records: list[dict[str, Any]] = []
    model.eval()
    with torch.inference_mode():
        for images, targets, indices in loader:
            probabilities = torch.softmax(model(images.to(device)), dim=1).cpu()
            for probability, target, index in zip(probabilities, targets, indices):
                row = rows[int(index)]
                seating_probability = float(probability[LABEL_INDEX["seating"]].item())
                raw_prediction = CLASS_ORDER[int(probability.argmax().item())]
                prediction = (
                    band_prediction(seating_probability, thresholds)
                    if thresholds is not None
                    else raw_prediction
                )
                records.append(
                    {
                        "scene_id": row["scene_id"],
                        "physical_scene_id": row["physical_scene_id"],
                        "slot_id": row["slot_id"],
                        "label": CLASS_ORDER[int(target)].lower(),
                        "raw_prediction": raw_prediction,
                        "prediction": prediction,
                        "flat_probability": float(probability[0].item()),
                        "seating_probability": seating_probability,
                    }
                )
    known = [row for row in records if row["prediction"] != "UNKNOWN"]
    correct = [row for row in records if row["prediction"].lower() == row["label"]]
    recalls = {}
    for label in ("flat", "seating"):
        class_rows = [row for row in records if row["label"] == label]
        recalls[label.upper()] = (
            sum(row["prediction"].lower() == label for row in class_rows)
            / max(1, len(class_rows))
        )
    return {
        "count": len(records),
        "accuracy_with_unknown_as_error": len(correct) / max(1, len(records)),
        "coverage": len(known) / max(1, len(records)),
        "per_class_recall": recalls,
        "unknown_count": len(records) - len(known),
        "records": records,
    }


def raw_metrics(evaluation: dict[str, Any]) -> tuple[float, float]:
    records = evaluation["records"]
    recalls = []
    for label in ("flat", "seating"):
        class_rows = [row for row in records if row["label"] == label]
        recalls.append(
            sum(row["raw_prediction"].lower() == label for row in class_rows)
            / len(class_rows)
        )
    accuracy = sum(
        row["raw_prediction"].lower() == row["label"] for row in records
    ) / len(records)
    return sum(recalls) / 2.0, accuracy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--warmup-epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--input-size", type=int, default=224)
    parser.add_argument("--seed", type=int, default=20260904)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.epochs < 2 or not 0 <= args.warmup_epochs < args.epochs:
        raise ValueError("Require epochs>=2 and 0<=warmup-epochs<epochs")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    dataset = args.dataset.expanduser().resolve()
    rows = load_rows(dataset)
    partitions = {
        split: [row for row in rows if row["split"] == split]
        for split in ("train", "validation", "holdout")
    }
    normalize = transforms.Normalize(
        mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
    )
    train_transform = transforms.Compose(
        [
            transforms.Resize((args.input_size, args.input_size)),
            # Seating may occur on any socket edge.  Mirroring is valid for
            # this independent seating task (unlike the direction classifier)
            # and prevents one controlled lip direction becoming a shortcut.
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomVerticalFlip(p=0.5),
            transforms.ColorJitter(brightness=0.06, contrast=0.06, saturation=0.03),
            transforms.ToTensor(),
            normalize,
        ]
    )
    evaluation_transform = transforms.Compose(
        [
            transforms.Resize((args.input_size, args.input_size)),
            transforms.ToTensor(),
            normalize,
        ]
    )
    train_dataset = ManifestDataset(dataset, partitions["train"], train_transform)
    class_counts = Counter(row["label"] for row in partitions["train"])
    sample_weights = [1.0 / class_counts[row["label"]] for row in partitions["train"]]
    generator = torch.Generator().manual_seed(args.seed)
    sampler = WeightedRandomSampler(
        sample_weights,
        num_samples=2 * max(class_counts.values()),
        replacement=True,
        generator=generator,
    )
    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        sampler=sampler,
        num_workers=args.num_workers,
        pin_memory=torch.cuda.is_available(),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(CLASS_ORDER))
    for parameter in model.features.parameters():
        parameter.requires_grad = False
    model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=args.learning_rate)
    best_macro_recall = -1.0
    best_accuracy = -1.0
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None

    for epoch in range(1, args.epochs + 1):
        if epoch == args.warmup_epochs + 1:
            for parameter in model.features[-4:].parameters():
                parameter.requires_grad = True
            optimizer = torch.optim.AdamW(
                [parameter for parameter in model.parameters() if parameter.requires_grad],
                lr=args.learning_rate * 0.25,
                weight_decay=1e-4,
            )
        model.train()
        if epoch <= args.warmup_epochs:
            model.features.eval()
        else:
            # Keep frozen BatchNorm statistics fixed.  Only the final four
            # feature blocks are allowed to adapt to the S22 seating texture.
            for block in model.features[:-4]:
                block.eval()
        for images, targets, _ in train_loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(images.to(device))
            loss = criterion(logits, targets.to(device))
            loss.backward()
            optimizer.step()
        validation_raw = evaluate(
            model,
            dataset,
            partitions["validation"],
            evaluation_transform,
            device,
        )
        train_raw = evaluate(
            model,
            dataset,
            partitions["train"],
            evaluation_transform,
            device,
        )
        validation_flat_recall = sum(
            row["raw_prediction"] == "FLAT"
            for row in validation_raw["records"]
        ) / len(validation_raw["records"])
        train_seating_rows = [
            row for row in train_raw["records"] if row["label"] == "seating"
        ]
        train_seating_recall = sum(
            row["raw_prediction"] == "SEATING" for row in train_seating_rows
        ) / len(train_seating_rows)
        macro_recall = (validation_flat_recall + train_seating_recall) / 2.0
        accuracy = min(validation_flat_recall, train_seating_recall)
        validation_probabilities = torch.tensor(
            [
                [row["flat_probability"], row["seating_probability"]]
                for row in validation_raw["records"]
            ],
            dtype=torch.float32,
        )
        validation_targets = torch.tensor(
            [LABEL_INDEX[row["label"]] for row in validation_raw["records"]],
            dtype=torch.long,
        )
        validation_loss = float(
            criterion(torch.log(validation_probabilities.clamp_min(1e-8)), validation_targets).item()
        )
        print(
            f"epoch={epoch:03d} device={device.type} "
            f"selection_balanced_recall={macro_recall:.4f} "
            f"validation_flat_recall={validation_flat_recall:.4f} "
            f"train_seating_recall={train_seating_recall:.4f} "
            f"validation_flat_loss={validation_loss:.6f}"
        )
        better = (
            macro_recall > best_macro_recall + 1e-9
            or (
                abs(macro_recall - best_macro_recall) <= 1e-9
                and (
                    accuracy > best_accuracy + 1e-9
                    or (
                        abs(accuracy - best_accuracy) <= 1e-9
                        and validation_loss < best_loss
                    )
                )
            )
        )
        if better:
            best_macro_recall = macro_recall
            best_accuracy = accuracy
            best_loss = validation_loss
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }

    if best_state is None:
        raise RuntimeError("Training produced no checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    validation_raw = evaluate(
        model, dataset, partitions["validation"], evaluation_transform, device
    )
    train_raw = evaluate(
        model, dataset, partitions["train"], evaluation_transform, device
    )
    thresholds = threshold_band(validation_raw["records"], train_raw["records"])
    train_evaluation = evaluate(
        model, dataset, partitions["train"], evaluation_transform, device, thresholds
    )
    validation_evaluation = evaluate(
        model, dataset, partitions["validation"], evaluation_transform, device, thresholds
    )
    # The fixed regression partition is intentionally touched only after the
    # checkpoint and thresholds are fixed.  It never feeds back into training.
    holdout_evaluation = evaluate(
        model, dataset, partitions["holdout"], evaluation_transform, device, thresholds
    )

    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    model_cpu = model.cpu().eval()
    scripted = torch.jit.trace(
        model_cpu, torch.zeros(1, 3, args.input_size, args.input_size)
    )
    model_path = output / "vrm_seating.torchscript.pt"
    torch.jit.save(scripted, str(model_path))
    evaluation_path = output / "vrm_seating_evaluation.json"
    evaluation_path.write_text(
        json.dumps(
            {
                "threshold_source": (
                    "independent_validation_flat_plus_development_train_seating"
                ),
                "holdout_used_for_model_selection": False,
                "holdout_role": "FIXED_REGRESSION_AFTER_FIRST_EVALUATION",
                "thresholds": thresholds,
                "train": train_evaluation,
                "validation": validation_evaluation,
                "holdout": holdout_evaluation,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    fixed_regression_passed = (
        holdout_evaluation["accuracy_with_unknown_as_error"] == 1.0
        and holdout_evaluation["unknown_count"] == 0
    )
    metadata = {
        "schema_version": 1,
        "task": "vrm_fixed_slot_seating",
        "class_order": list(CLASS_ORDER),
        "input_size": args.input_size,
        "crop_pipeline": VRM_SEATING_CROP_PIPELINE,
        **thresholds,
        "authority": "ADVISORY_ONLY",
        "validated": False,
        "model_release_id": "vrm_seating_candidate_v4",
        "runtime_enabled": False,
        "candidate_status": "DEVELOPMENT_ONLY_PENDING_CROSS_SCENE_VALIDATION",
        "fixed_regression_passed": fixed_regression_passed,
        "holdout_first_evaluation_consumed": True,
        "validation_policy": (
            "independent flat false-positive validation plus fixed VRM05 "
            "seating regression"
        ),
        "holdout_used_for_model_selection": False,
        "best_validation_macro_recall": best_macro_recall,
        "best_validation_accuracy": best_accuracy,
        "best_validation_loss": best_loss,
        "dataset": str(dataset),
        "dataset_counts": {
            split: Counter(row["label"] for row in split_rows)
            for split, split_rows in partitions.items()
        },
        "physical_scenes": {
            split: sorted({row["physical_scene_id"] for row in split_rows})
            for split, split_rows in partitions.items()
        },
        "evaluation": str(evaluation_path),
        "restriction": (
            "ADVISORY_ONLY: only two development seating setups and one fixed VRM05 "
            "regression setup exist; fresh independently reseated defects are required."
        ),
        "robot_command_sent": False,
        "conveyor_command_sent": False,
    }
    metadata_path = output / "vrm_seating.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, default=dict) + "\n",
        encoding="utf-8",
    )
    print(f"VRM_SEATING_MODEL={model_path}")
    print(f"VRM_SEATING_METADATA={metadata_path}")
    print(f"VRM_SEATING_EVALUATION={evaluation_path}")
    print(f"VALIDATION_SEPARATED={str(thresholds['validation_separated']).lower()}")
    print(f"FIXED_REGRESSION_PASSED={str(fixed_regression_passed).lower()}")
    print("MODEL_AUTHORITY=ADVISORY_ONLY")


if __name__ == "__main__":
    main()

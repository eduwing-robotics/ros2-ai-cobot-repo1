#!/usr/bin/env python3
"""Train one PatchCore memory bank per PCB component type."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import torch

from train_pcb_patchcore import json_safe, save_prediction_visualizations


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = (
    PROJECT_DIR / "vision_assembly/inspection/datasets/pcb_components_v1"
)
DEFAULT_OUTPUT = PROJECT_DIR / "runtime/inspection/patchcore/pcb_components_v1"
COMPONENTS = (
    "gpu", "hbm", "power_module", "vrm", "inductor", "smd_capacitor"
)


def _image_size(directory: Path) -> tuple[int, int]:
    first = next(iter(sorted(directory.glob("*.png"))), None)
    if first is None:
        raise RuntimeError(f"No training images in {directory}")
    image = cv2.imread(str(first), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Cannot decode {first}")
    return image.shape[0], image.shape[1]


def train_component(
    component: str,
    dataset_root: Path,
    output_root: Path,
    num_workers: int,
    coreset_ratio: float,
    abnormal_dir: str,
    layers: tuple[str, ...],
    backbone_checkpoint: Path | None = None,
) -> dict:
    from anomalib.data import Folder
    from anomalib.engine import Engine
    from anomalib.models import Patchcore

    dataset = dataset_root / component
    output = output_root / component
    output.mkdir(parents=True, exist_ok=True)
    counts = {
        "train_good": len(list((dataset / "train/good").glob("*.png"))),
        "test_good": len(list((dataset / "test/good").glob("*.png"))),
        "controlled_defect": len(
            list((dataset / abnormal_dir).glob("*.png"))
        ),
    }
    if min(counts.values()) <= 0:
        raise RuntimeError(f"Incomplete {component} dataset: {counts}")
    height, width = _image_size(dataset / "train/good")

    datamodule = Folder(
        name=f"pcb_{component}_v1",
        root=dataset,
        normal_dir="train/good",
        normal_test_dir="test/good",
        abnormal_dir=abnormal_dir,
        normal_split_ratio=0.0,
        train_batch_size=4,
        eval_batch_size=4,
        num_workers=num_workers,
        test_split_mode="from_dir",
        val_split_mode="from_test",
        val_split_ratio=0.25,
        seed=42,
    )
    pre_processor = Patchcore.configure_pre_processor(image_size=(height, width))
    model = Patchcore(
        backbone="wide_resnet50_2",
        layers=layers,
        pre_trained=backbone_checkpoint is None,
        coreset_sampling_ratio=coreset_ratio,
        num_neighbors=9,
        pre_processor=pre_processor,
        visualizer=False,
    )
    if backbone_checkpoint is not None:
        # Trusted local project checkpoint: reuse ONLY frozen feature weights.
        # Never import the old memory bank, postprocessing thresholds or fit state.
        state = torch.load(backbone_checkpoint, map_location='cpu', weights_only=False)['state_dict']
        prefix = 'model.feature_extractor.'
        features = {k[len(prefix):]: v for k, v in state.items() if k.startswith(prefix)}
        if not features:
            raise RuntimeError('No feature extractor weights in local checkpoint')
        model.model.feature_extractor.load_state_dict(features, strict=True)
    engine = Engine(
        accelerator="gpu",
        devices=1,
        max_epochs=1,
        default_root_dir=output,
        logger=False,
        enable_model_summary=False,
    )
    engine.fit(model=model, datamodule=datamodule)
    metrics = engine.test(model=model, datamodule=datamodule)
    predictions = engine.predict(
        model=model,
        data_path=dataset / abnormal_dir,
        return_predictions=True,
    )
    visualization_count = save_prediction_visualizations(predictions, output)
    summary = {
        "status": "candidate_unverified",
        "component": component,
        "model": "PatchCore/wide_resnet50_2",
        "feature_layers": list(layers),
        "input_size": [height, width],
        "dataset_counts": counts,
        "metrics": json_safe(metrics),
        "visualization_count": visualization_count,
        "decision_warning": (
            "Controlled-defect coverage is still too small. Metrics and the "
            "automatic threshold are exploratory and must not control PASS/FAIL."
        ),
    }
    (output / "component_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--component", choices=("all",) + COMPONENTS, default="all")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--coreset-ratio", type=float, default=0.1)
    parser.add_argument("--abnormal-dir", default="unverified/mixed_defect")
    parser.add_argument(
        "--layers",
        default="layer2,layer3",
        help="Comma-separated backbone layers; crack inspection uses layer1,layer2.",
    )
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; component PatchCore requires the GPU")
    torch.set_float32_matmul_precision("high")
    selected = COMPONENTS if args.component == "all" else (args.component,)
    layers = tuple(item.strip() for item in args.layers.split(",") if item.strip())
    if not layers:
        raise RuntimeError("--layers must contain at least one feature layer")
    summaries = []
    for component in selected:
        print(f"\n=== TRAIN COMPONENT PATCHCORE: {component} ===", flush=True)
        summaries.append(train_component(
            component,
            args.dataset.expanduser().resolve(),
            args.output.expanduser().resolve(),
            args.num_workers,
            args.coreset_ratio,
            args.abnormal_dir,
            layers,
        ))
    suite = {
        "schema_version": 1,
        "status": "candidate_unverified",
        "components": summaries,
    }
    suite_path = args.output.expanduser().resolve() / "suite_summary.json"
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite_path.write_text(
        json.dumps(suite, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"COMPONENT_PATCHCORE_RESULT={suite_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create a frame-grouped train/val split for the tray segmentation dataset."""

import argparse
import json
import shutil
from pathlib import Path


NAMES = {0: "black_block", 1: "marked_white", 2: "right_white_brown",
         3: "long_orange", 4: "gpu", 5: "hbm"}


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=root / "datasets/tray_segmentation/yolo")
    parser.add_argument("--val-frames", type=int, default=4)
    parser.add_argument("--test-frames", type=int, default=0)
    args = parser.parse_args()
    source_images = args.dataset / "images" / "all"
    source_labels = args.dataset / "labels" / "all"
    images = sorted(source_images.glob("*.jpg"))
    def frame_and_part(path):
        fields = path.stem.split("__")
        if len(fields) < 2:
            raise RuntimeError(f"Invalid labeled image name: {path.name}")
        return "__".join(fields[:-1]), fields[-1]

    frames = sorted({frame_and_part(path)[0] for path in images})
    if len(frames) <= args.val_frames + args.test_frames:
        raise RuntimeError("Not enough labeled frames for the requested split")
    frame_parts = {frame: set() for frame in frames}
    for image in images:
        frame, part = frame_and_part(image)
        frame_parts[frame].add(part)
    # Select validation/test frames round-robin across capture sessions so new
    # hard examples are measured instead of being placed only in training.
    session_frames = {}
    for frame in frames:
        session = frame.split("__frame_", 1)[0] if "__frame_" in frame else "legacy"
        session_frames.setdefault(session, []).append(frame)
    for session in session_frames:
        session_frames[session].sort(key=lambda frame: (-len(frame_parts[frame]), frame))
    ranked = []
    while any(session_frames.values()):
        for session in sorted(session_frames):
            if session_frames[session]:
                ranked.append(session_frames[session].pop(0))
    test = set(ranked[:args.test_frames])
    val = set(ranked[args.test_frames:args.test_frames + args.val_frames])
    split_counts = {"train": 0, "val": 0, "test": 0}
    instance_counts = {"train": 0, "val": 0, "test": 0}
    for split in split_counts:
        for kind in ("images", "labels"):
            target = args.dataset / kind / split
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
    for image in images:
        frame, _ = frame_and_part(image)
        split = "test" if frame in test else ("val" if frame in val else "train")
        label = source_labels / f"{image.stem}.txt"
        if not label.exists():
            raise RuntimeError(f"Missing label: {label}")
        shutil.copy2(image, args.dataset / "images" / split / image.name)
        shutil.copy2(label, args.dataset / "labels" / split / label.name)
        split_counts[split] += 1
        instance_counts[split] += len([row for row in label.read_text().splitlines() if row.strip()])
    yaml = args.dataset / "dataset.yaml"
    yaml.write_text(
        f"path: {args.dataset.resolve()}\n"
        "train: images/train\nval: images/val\ntest: images/test\n\n"
        "names:\n" + "".join(f"  {key}: {value}\n" for key, value in NAMES.items()),
        encoding="utf-8",
    )
    summary = {
        "frame_split": {
            "train": [f for f in frames if f not in val and f not in test],
            "val": sorted(val), "test": sorted(test)
        },
        "image_counts": split_counts,
        "instance_counts": instance_counts,
    }
    (args.dataset / "split_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

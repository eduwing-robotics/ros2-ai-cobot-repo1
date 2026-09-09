"""Offline raw-evidence replay. Does not change runtime votes or fit thresholds."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

import cv2
import numpy as np

from hbm_individual_pins import compare


def simulate_gain(sample, gain):
    """Synthetic pixel scaling only, not a physical exposure simulation."""
    if not np.isfinite(gain) or not 0 < gain <= 1:
        raise ValueError("Gain must be finite and in (0, 1]")
    return np.rint(sample.astype(np.float32) * gain).astype(np.uint8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", required=True, type=Path)
    parser.add_argument("--gain", action="append", type=float,
                        help="Synthetic intensity gains in (0,1]; default original only")
    parser.add_argument("--output", type=Path, help="New JSON file; refuses overwrite")
    args = parser.parse_args()
    gains = args.gain or [1.0]
    for gain in gains:
        simulate_gain(np.zeros((1, 1, 3), np.uint8), gain)
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "vision_assembly/config/hbm_pin_reference.json").read_text())
    results = []
    for run in args.run:
        for slot_id, entry in sorted(manifest["slots"].items()):
            ref_path = root / entry["path"]
            ref_bytes = ref_path.read_bytes()
            if hashlib.sha256(ref_bytes).hexdigest() != entry["sha256"]:
                raise ValueError(f"Reference hash mismatch: {slot_id}")
            sample_path = run / "fixed_slots/hbm" / f"{slot_id}.png"
            sample = cv2.imread(str(sample_path))
            reference = cv2.imread(str(ref_path))
            if sample is None or reference is None:
                raise ValueError(f"Missing image: {sample_path}")
            source_hash = hashlib.sha256(sample_path.read_bytes()).hexdigest()
            for gain in gains:
                for side in compare(reference, simulate_gain(sample, gain)):
                    ratios = side["evidence_ratio"]
                    visible = [v for v in ratios if v >= .3]
                    results.append({
                        "run": str(run), "slot_id": slot_id, "side": side["side"],
                        "sample_sha256": source_hash, "gain": gain,
                        "synthetic": gain != 1.0,
                        "status": side["status"], "missing_indices": side["missing_indices"],
                        "ratios": ratios,
                        "visible_anchor_count": len(visible),
                        "visible_anchor_median": median(visible) if visible else None,
                        "truth": "UNASSIGNED_REQUIRES_EXTERNAL_PROVENANCE",
                    })
    payload = json.dumps({"authority": "OFFLINE_DIAGNOSTIC_ONLY", "rows": results}, indent=2)
    if args.output:
        with args.output.open("x") as stream:
            stream.write(payload + "\n")
        print(args.output)
    else:
        print(payload)


if __name__ == "__main__":
    main()

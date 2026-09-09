"""Development replay; never calls normal boards defective to fit the rule."""
from pathlib import Path
import json
import hashlib
from copy import deepcopy
from main import build_advisory_candidates
from smd01_small_lip import RULE

ROOT = Path(__file__).resolve().parents[2]


def audit():
    base = ROOT / "runtime/inspection"
    cases = [(Path(c["report"]), c["truth"]) for c in json.loads(
        (base / "smd01_small_lip_candidate_20260907.json").read_text())["results"][0]["cases"]]
    for stamp, truth in [("121829_086609", "defect"), ("122104_842085", "normal"),
                         ("130800_689089", "defect"), ("131107_594576", "normal")]:
        cases.append((base / f"hybrid_fixed_slot/20260907_{stamp}/hybrid_report.json", truth))
    for folder, truth in [
        ("smd01_lip_validation_20260908_132035/20260908_132108_768224", "defect"),
        ("smd01_recovery_20260908_132402/20260908_132425_543863", "normal")]:
        cases.append((base / folder / "hybrid_report.json", truth))
    event = json.loads((base / "api/d24beed9-4df3-422c-8707-2f67f6918df8/event.json").read_text())
    cases.extend((Path(a["report"]), "normal") for a in event["attempts"])
    rows = []
    old = RULE["patchcore_min"]
    try:
        for path, truth in cases:
            d = json.loads(path.read_text())
            image = Path(d["input_image"])
            if hashlib.sha256(image.read_bytes()).hexdigest() != d["input_sha256"]:
                raise ValueError("Source changed")
            item = {"report": str(path), "truth": truth}
            for score in (.10, .14):
                RULE["patchcore_min"] = score
                candidates = build_advisory_candidates(deepcopy(d["slots"]))
                item[str(score)] = any(c["slot_id"] == "smd_capacitor_01" for c in candidates)
            rows.append(item)
    finally:
        RULE["patchcore_min"] = old
    return {"rows": rows, "independent_validation": False,
            "note": "Reused developmental data and archived providers; threshold proposed after observing normal warnings."}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))

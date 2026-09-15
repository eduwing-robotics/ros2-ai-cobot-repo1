"""Offline evidence inventory, not inference, calibration, or an accuracy claim.

Only the three explicit JSON inputs are read. Image hashes are source assertions,
not reverified pixels. Hashless records never acquire a hash from a scene name.
Legacy expected_pose is retained as position evidence with ambiguous semantics;
it does not establish measured in-plane displacement or physical seating.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

SOURCES = (
    "runtime/inspection/confirmed_controls_20260908/audit.json",
    "runtime/inspection/vrm_controls_20260908/audit.json",
    "vision_assembly/config/vrm_presence_context_holdout_20260905.json",
)
OUTPUT = "runtime/inspection/parallel_completion_20260908/registry"
TASKS = ("presence", "position", "physical_seating", "process_clearance",
         "orientation", "pins", "surface_crack")
TRACKS = {"seating": "physical_seating", "direction": "orientation",
          "in_plane_position": "position", **{t: t for t in TASKS}}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def normalized(task, value):
    if task not in TASKS or not isinstance(value, str):
        return None
    if task == "presence":
        return value if value in ("PRESENT", "EMPTY") else None
    return {"NORMAL": "PASS", "NORMAL_POSITION": "PASS", "DEFECT": "FAIL",
            "PASS": "PASS", "FAIL": "FAIL",
            "FLAT_AGAINST_RIGHT_WALL": "PASS"}.get(value)


def build_registry(documents):
    """Accept {source_path: parsed_json}; preserve every source row losslessly."""
    cases, scenes, sources = {}, [], []

    def add(source, pointer, row, slot, task, raw, semantics):
        sha = row.get("image_sha256") or row.get("input_sha256") or row.get("source_hash")
        valid = isinstance(sha, str) and re.fullmatch(r"[0-9a-fA-F]{64}", sha)
        # Source-local identity is deliberately NOT cross-source image identity.
        fallback = row.get("physical_scene_id") or row.get("scene") or row.get("image") or row.get("report") or pointer
        identity = "sha256:" + sha.lower() if valid else "unverified:" + digest([source, fallback])
        key = (identity, slot, task)
        case = cases.setdefault(key, {
            "case_id": digest(key), "image_identity": identity,
            "image_sha256": sha.lower() if valid else None,
            "identity_status": "SOURCE_ASSERTED_SHA256" if valid else "HASHLESS_OR_INVALID",
            "slot": slot, "task": task, "evidence": [],
            "independent_validation": False, "authority": "ADVISORY_ONLY",
        })
        case["evidence"].append({"source": source, "pointer": pointer,
                                 "raw_label": raw, "label": normalized(task, raw),
                                 "semantics": semantics, "record": row})

    for source, doc in documents.items():
        sources.append({"path": source, "parsed_content_sha256": digest(doc),
                        "metadata": {k: v for k, v in doc.items()
                                     if k not in ("rows", "scenes", "normal_position_controls")}})
        for i, row in enumerate(doc.get("rows", [])):
            ptr = f"/rows/{i}"
            if "track" in row:
                task = TRACKS.get(row["track"], "unmapped:" + str(row["track"]))
                add(source, ptr, row, row["slot"], task, row.get("truth"), "explicit_audit_track")
            else:
                add(source, ptr, row, row["slot"], "presence", row.get("presence_truth"), "presence_only")
                if row.get("expected_pose") is not None:
                    add(source, ptr, row, row["slot"], "position", row["expected_pose"], "legacy_pose_not_metric_position_or_seating")
        for i, row in enumerate(doc.get("normal_position_controls", [])):
            add(source, f"/normal_position_controls/{i}", row, row["slot"], "position", row.get("truth"), "explicit_normal_position")
        for i, row in enumerate(doc.get("scenes", [])):
            ptr = f"/scenes/{i}"
            scenes.append({"source": source, "pointer": ptr, "record": row})
            for field, task in (("labels", "presence"), ("expected_pose", "position")):
                for slot, label in row.get(field, {}).items():
                    add(source, ptr, row, slot, task, label,
                        "presence_only" if task == "presence" else "legacy_pose_not_metric_position_or_seating")
            review = row.get("process_position_review")
            if review:
                add(source, ptr, row, review["slot"], "physical_seating", review.get("physical_seating"), "user_physical_review_not_height_measurement")
                # Requested disposition is NOT a verified collision label.
                add(source, ptr, row, review["slot"], "process_clearance", review.get("status"), "unverified_process_review_not_seating_defect")

    result = []
    for key in sorted(cases):
        case = cases[key]
        case["evidence"].sort(key=lambda e: (e["source"], e["pointer"], digest(e)))
        labels = sorted({e["label"] for e in case["evidence"] if e["label"] is not None})
        unknown = sum(e["label"] is None for e in case["evidence"])
        case.update(labels=labels, unknown_label_observations=unknown,
                    status="CONFLICT" if len(labels) > 1 else "UNKNOWN" if unknown or not labels else "LABELLED",
                    resolved_label=labels[0] if len(labels) == 1 and not unknown else None,
                    observation_count=len(case["evidence"]))
        result.append(case)

    uncovered = []
    for slot in sorted({c["slot"] for c in result}):
        for task in TASKS:
            rows = [c for c in result if c["slot"] == slot and c["task"] == task]
            usable = [c for c in rows if c["status"] == "LABELLED" and c["image_sha256"]]
            labels = sorted({c["resolved_label"] for c in usable})
            required = {"PRESENT", "EMPTY"} if task == "presence" else {"PASS", "FAIL"}
            uncovered.append({"slot": slot, "task": task,
                              "source_labelled_hashed_cases": len(usable),
                              "missing_label_classes": sorted(required - set(labels)),
                              "exact_model_verified_cases": 0,
                              "actions": [
                                  "Resolve conflicting/unknown labels and bind hashless evidence to verified image bytes.",
                                  "Collect missing classes with task-specific ground truth; pose labels alone do not measure displacement, height or clearance.",
                                  "Record exact weights SHA256, preprocessing, thresholds, calibration and per-case predictions; audit train/development overlap and freeze before fresh scene collection.",
                              ]})
    counts = {
        "cases": len(result), "observations": sum(c["observation_count"] for c in result),
        "merged_observations": sum(c["observation_count"] - 1 for c in result),
        "unique_source_asserted_image_hashes": len({c["image_sha256"] for c in result if c["image_sha256"]}),
        "hashless_cases": sum(c["image_sha256"] is None for c in result),
        "statuses": dict(Counter(c["status"] for c in result)),
        "conflicts": sum(c["status"] == "CONFLICT" for c in result),
        "tasks": dict(Counter(c["task"] for c in result)),
        "task_label_counts": {task: dict(Counter(
            c["resolved_label"] or c["status"] for c in result if c["task"] == task
        )) for task in TASKS},
        "independent_validation_cases": 0, "exact_model_verified_cases": 0,
    }
    return {"schema_version": 1, "authority": "ADVISORY_ONLY", "counts": counts,
            "sources": sources, "cases": result, "scenes": scenes,
            "uncovered_tasks": uncovered,
            "unlabelled_scene_actions": [
                {"source": s["source"], "pointer": s["pointer"],
                 "scene": s["record"].get("physical_scene_id"),
                 "action": "Obtain explicit per-slot task labels; motion observations and absence of warnings are not ground truth."}
                for s in scenes if not s["record"].get("labels") and not s["record"].get("expected_pose")
            ],
            "limitations": [
                "No model run or exact-model accuracy measurement; archived predictions remain provenance only.",
                "Unique image hashes and multiple slots are not independent physical trials.",
                "Hashless records remain provisional even when their scene name matches a hashed replay.",
                "Explicit corrections are preserved, not silently propagated to other frames or used to overwrite contradictory sources.",
                "Only named slots inventoried; obtain the authoritative 25-slot roster to expand missing-task coverage. Other-20-empty notes are retained but not expanded by guessing slot IDs.",
                "Legacy expected_pose combines position/orientation/seating semantics; no metric task certification is inferred.",
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    documents, hashes = {}, {}
    for name in SOURCES:
        data = (args.root / name).read_bytes()
        documents[name] = json.loads(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    registry = build_registry(documents)
    for source in registry["sources"]:
        source["file_sha256"] = hashes[source["path"]]
    output = args.root / OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (("registry.json", registry),
                       ("summary.json", {k: v for k, v in registry.items() if k not in ("cases", "scenes") })):
        (output / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(registry["counts"], indent=2))


if __name__ == "__main__":
    main()

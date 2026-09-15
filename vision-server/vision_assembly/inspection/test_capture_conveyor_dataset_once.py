import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np


MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import capture_conveyor_dataset_once as pipeline  # noqa: E402


def _rotate_link(link: Path, target: Path) -> None:
    link.unlink(missing_ok=True)
    link.symlink_to(target)


def test_capture_archives_unverified_sample_without_inspection(monkeypatch, tmp_path):
    names = {
        "raw": "s22_telephoto_latest.jpg",
        "roi": "s22_inspection_roi_latest.png",
        "roi_metadata": "s22_inspection_roi_latest.json",
        "upright": "s22_telephoto_upright_latest.png",
        "debug": "s22_inspection_roi_debug_latest.jpg",
    }
    links = {key: tmp_path / value for key, value in names.items()}
    for key, link in links.items():
        old = tmp_path / f"old_{key}.dat"
        old.write_bytes(b"old")
        _rotate_link(link, old)

    def fake_capture(_script):
        stamp = "20260831_190000"
        image = np.full((40, 60, 3), 80, np.uint8)
        for key, link in links.items():
            suffix = {
                "raw": ".jpg",
                "roi": ".png",
                "roi_metadata": ".json",
                "upright": ".png",
                "debug": ".jpg",
            }[key]
            target = tmp_path / f"s22_{key}_{stamp}{suffix}"
            if key == "roi_metadata":
                target.write_text(
                    json.dumps({"detector": {"rectangularity": 0.91}}),
                    encoding="utf-8",
                )
            else:
                assert cv2.imwrite(str(target), image)
            _rotate_link(link, target)

    monkeypatch.setattr(pipeline, "run_capture", fake_capture)
    args = argparse.Namespace(
        capture_script=tmp_path / "capture.sh",
        raw=links["raw"],
        roi=links["roi"],
        roi_metadata=links["roi_metadata"],
        upright=links["upright"],
        debug=links["debug"],
        dataset_root=tmp_path / "dataset",
        split="unverified",
        lighting="evening_indoor",
        board_state="known_defect",
        known_defects=["missing_smd"],
        event_output=tmp_path / "event.json",
        source_topic="/test/stop_trigger",
    )

    event = pipeline.run_pipeline(args)

    assert event["final_status"] == "CAPTURED_UNVERIFIED"
    manifest = json.loads(Path(event["manifest"]).read_text(encoding="utf-8"))
    assert manifest["classification"] == "UNVERIFIED"
    assert manifest["normal_training_allowed"] is False
    assert manifest["camera_recipe"]["flash"] == "off"
    assert manifest["board_annotation"] == {
        "state": "known_defect",
        "known_defects": ["missing_smd"],
        "human_verified": False,
    }
    assert Path(event["roi_image"]).is_file()
    assert len((Path(event["manifest"]).parents[1] / "index.jsonl").read_text().splitlines()) == 1

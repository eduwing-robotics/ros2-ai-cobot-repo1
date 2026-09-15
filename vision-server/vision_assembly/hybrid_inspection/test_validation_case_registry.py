"""Standard-library tests; no images, inference, hardware or network."""
import unittest

from vision_assembly.hybrid_inspection.validation_case_registry import build_registry


def row(truth="NORMAL", **kwargs):
    return {"slot": "vrm_02", "track": "seating", "truth": truth,
            "input_sha256": "a" * 64, **kwargs}


class RegistryTests(unittest.TestCase):
    def test_conflicts_never_last_write_wins(self):
        for rows in ([row(), row("DEFECT")], [row("DEFECT"), row()]):
            c = build_registry({"audit": {"rows": rows}})["cases"][0]
            self.assertEqual(c["status"], "CONFLICT")
            self.assertIsNone(c["resolved_label"])
            self.assertEqual(c["labels"], ["FAIL", "PASS"])

    def test_duplicate_replays_deduplicate_cases_not_provenance(self):
        r = build_registry({"a": {"rows": [row(), row(report="replay")]},
                            "b": {"rows": [row()]}})
        self.assertEqual(r["counts"]["cases"], 1)
        self.assertEqual(r["counts"]["merged_observations"], 2)
        self.assertEqual(len(r["cases"][0]["evidence"]), 3)
        self.assertEqual(r["counts"]["independent_validation_cases"], 0)

    def test_unknown_labels_do_not_become_normal(self):
        for value in (None, "UNKNOWN", "maybe", 7, {"bad": True}):
            c = build_registry({"a": {"rows": [row(value)]}})["cases"][0]
            self.assertEqual(c["status"], "UNKNOWN")
            self.assertIsNone(c["resolved_label"])

    def test_unknown_plus_known_is_not_silent_resolution(self):
        c = build_registry({"a": {"rows": [row(), row("UNKNOWN")]}})["cases"][0]
        self.assertEqual(c["status"], "UNKNOWN")

    def test_unknown_track_is_not_validated(self):
        c = build_registry({"a": {"rows": [row(track="mystery")]}})["cases"][0]
        self.assertEqual(c["status"], "UNKNOWN")

    def test_hashless_scene_not_merged_into_hashed_replay(self):
        scene = {"physical_scene_id": "scene", "labels": {"vrm_02": "PRESENT"}}
        audit = {"scene": "scene", "slot": "vrm_02", "source_hash": "a" * 64,
                 "presence_truth": "PRESENT"}
        r = build_registry({"holdout": {"scenes": [scene, scene]}, "audit": {"rows": [audit]}})
        self.assertEqual(r["counts"]["cases"], 2)
        self.assertEqual(r["counts"]["hashless_cases"], 1)

    def test_anonymous_hashless_rows_not_conflated(self):
        r = build_registry({"a": {"rows": [row(input_sha256=None), row(input_sha256=None)]}})
        self.assertEqual(r["counts"]["cases"], 2)

    def test_tasks_and_correction_preserved(self):
        scene = {"image_sha256": "a" * 64, "labels": {"vrm_02": "PRESENT"},
                 "expected_pose": {"vrm_02": "PASS"}, "label_correction": "explicit user correction",
                 "process_position_review": {"slot": "vrm_02", "physical_seating": "FLAT_AGAINST_RIGHT_WALL",
                                             "status": "UNKNOWN", "user_requested_disposition": "POSITION_ERROR"}}
        r = build_registry({"holdout": {"scenes": [scene]}})
        cases = {c["task"]: c for c in r["cases"]}
        self.assertEqual(set(cases), {"presence", "position", "physical_seating", "process_clearance"})
        self.assertEqual(cases["physical_seating"]["resolved_label"], "PASS")
        self.assertEqual(cases["process_clearance"]["status"], "UNKNOWN")
        self.assertEqual(cases["position"]["evidence"][0]["record"]["label_correction"], scene["label_correction"])

    def test_unlabelled_scene_retained_and_no_model_authority(self):
        r = build_registry({"h": {"scenes": [{"physical_scene_id": "bump", "labels": {}}]}})
        self.assertEqual(len(r["scenes"]), 1)
        self.assertEqual(r["counts"]["cases"], 0)
        self.assertEqual(r["counts"]["exact_model_verified_cases"], 0)
        self.assertEqual(len(r["unlabelled_scene_actions"]), 1)


if __name__ == "__main__":
    unittest.main()

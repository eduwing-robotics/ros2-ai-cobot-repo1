import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from model_completion_gate import _report_audit, build_gate


def _complete_report(slot_types):
    stages = {}
    for slot_id, component_type in slot_types.items():
        required = ["presence", "pose", "orientation", "surface"]
        if component_type in {"GPU", "HBM"}:
            required.append("pins")
        stages[slot_id] = {
            name: {"status": "PASS", "authority": "AUTHORITATIVE", "confidence": 0.99}
            for name in required
        }
    return {
        "status": "UNKNOWN",
        "slots": [
            {"slot_id": slot_id, "component_type": component_type, "stages": stages[slot_id]}
            for slot_id, component_type in slot_types.items()
        ],
        "capture_quality": {"policy": {"validated": True}},
    }


def test_report_audit_requires_authoritative_required_stages():
    slot_types = {f"slot_{index:02d}": "VRM" for index in range(25)}
    report = _complete_report(slot_types)
    report["slots"][0]["stages"]["surface"]["authority"] = "ADVISORY_ONLY"
    result, blockers = _report_audit(report, set(slot_types), slot_types)
    assert not result["ready"]
    assert "report:required_stage_not_authoritative_pass" in blockers
    assert result["missing_or_non_authoritative"]["slot_00"] == ["surface"]


def test_report_audit_accepts_a_complete_synthetic_matrix():
    slot_types = {"ai_gpu": "GPU"}
    slot_types.update({f"hbm_{index:02d}": "HBM" for index in range(1, 9)})
    slot_types.update({f"vrm_{index:02d}": "VRM" for index in range(1, 6)})
    slot_types.update({f"power_module_{index:02d}": "Power Module" for index in range(1, 5)})
    slot_types.update({f"inductor_{index:02d}": "Inductor" for index in range(1, 3)})
    slot_types.update({f"smd_capacitor_{index:02d}": "SMD Capacitor" for index in range(1, 6)})
    result, blockers = _report_audit(_complete_report(slot_types), set(slot_types), slot_types)
    assert len(slot_types) == 25
    assert result["ready"]
    assert blockers == []


def test_build_gate_is_read_only_and_reports_missing_release_artifacts(tmp_path: Path):
    contract = tmp_path / "contract.json"
    config = tmp_path / "config.json"
    layout = tmp_path / "layout.json"
    contract.write_text(json.dumps({
        "contract_id": "test_contract",
        "stages": [{"id": "capture_quality", "current_status": "PARTIALLY_IMPLEMENTED"}],
    }), encoding="utf-8")
    layout.write_text(json.dumps({
        "placements": [
            {"slot_id": f"slot_{index:02d}", "component_type": "VRM"}
            for index in range(25)
        ]
    }), encoding="utf-8")
    config.write_text(json.dumps({"board_layout": str(layout)}), encoding="utf-8")
    result = build_gate(
        contract_path=contract,
        config_path=config,
        presence_models=tmp_path / "presence",
        patchcore_models=tmp_path / "patchcore",
        project_dir=tmp_path,
    )
    assert result["contract_id"] == "test_contract"
    assert not result["ready_for_production"]
    assert "capture_quality" in result["blockers"]
    assert any(item.startswith("patchcore_threshold:") for item in result["blockers"])
    assert not (tmp_path / "presence").exists()
    assert not (tmp_path / "patchcore").exists()

from __future__ import annotations

from types import SimpleNamespace
import hashlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "vision_assembly" / "scripts"
sys.path.insert(0, str(SCRIPTS))

executor = pytest.importorskip("execute_full_fixed_cycle")


def test_partial_scope_selection_uses_slot_not_list_offset():
    items=[{'slot_code':s} for s in ['HBM-02','HBM-03','PM-02']]
    assert executor.select_items(items,'HBM-02',None,None)==items[:1]
    assert executor.select_items(items,None,'HBM-03','PM-02')==items[1:]


def test_midpoint_keeps_equivalent_roll_level_and_slot_height():
    item=gpu_item()
    item['slot_code']='HBM-04'
    item['transfer_z_mm']=400.0
    item['place_final_tcp'][3]=180.0
    route=executor.build_tcp_route([item],[-528,-61,337.9,-180,0,90],350,resume_after_grasp=False)
    mids=[w for _,w in route if w.label=='place_combined_xy_abc_midpoint']
    assert len(mids)==2
    for w in mids:
        assert abs(w.tcp[3])==pytest.approx(180)
        assert w.tcp[4]==pytest.approx(0)
        assert w.tcp[2]==400


def test_ind_empty_transfer_unwinds_and_stays_level():
    item=gpu_item();item['slot_code']='IND-02';item['pick_final_tcp'][5]=-179.8
    route=executor.build_tcp_route([item],[0,-500,200,180,0,0],350,resume_after_grasp=False)
    mids=[w for _,w in route if w.label=='pick_combined_xy_abc_midpoint']
    assert len(mids)==2
    assert -181<mids[1].tcp[5]<mids[0].tcp[5]<0
    assert all(abs(w.tcp[3])==pytest.approx(180) and w.tcp[2]==350 for w in mids)


def gpu_item() -> dict:
    return {
        "slot_code": "GPU-01",
        "part_type": "gpu",
        "pick_final_tcp": [-519.0, -158.0, -48.7, -180.0, 0.0, 91.6],
        "place_final_tcp": [34.6, -520.5, 88.46, -180.0, 0.0, -179.1],
        "tray_open_position": 70,
        "grip_position": 65,
        "release_position": 70,
        "placement_orientation": {
            "mode": "align_actual_carried_axis_to_current_slot_axis",
        },
    }


def test_speed_profile_and_resume_begin_at_carry_safe() -> None:
    item = gpu_item()
    start = [-528.0, -61.0, 337.9, -180.0, 0.0, 90.0]
    route = executor.build_tcp_route(
        [item], start, 350.0, resume_after_grasp=False
    )
    labels = [waypoint.label for _, waypoint in route]
    assert len(labels) == 14
    assert labels[6] == "post_grasp_proof_lift_100mm_vertical"
    speeds = {"travel": 25, "combined_rotation": 25, "vertical": 10}
    assert executor.waypoint_speed("pick_hover_100mm_vertical", speeds) == 25
    assert executor.waypoint_speed("pick_approach_50mm_vertical", speeds) == 25
    assert executor.waypoint_speed("pick_final_50mm_vertical", speeds) == 10
    assert executor.waypoint_speed("post_grasp_lift_50mm_vertical", speeds) == 10
    assert (
        executor.waypoint_speed(
            "post_grasp_proof_lift_100mm_vertical", speeds
        )
        == 25
    )
    assert executor.waypoint_speed("place_approach_50mm_vertical", speeds) == 25
    assert executor.waypoint_speed("place_final_50mm_vertical", speeds) == 10
    assert executor.waypoint_speed("post_release_lift_50mm_vertical", speeds) == 10
    assert executor.waypoint_speed("post_release_lift_100mm_vertical", speeds) == 25

    resumed = executor.build_tcp_route(
        [item], start, 350.0, resume_after_grasp=True
    )
    resumed_labels = [waypoint.label for _, waypoint in resumed]
    assert resumed_labels[0] == "carry_safe_vertical"
    assert len(resumed_labels) == 7
    assert not any(label.startswith("pick_") for label in resumed_labels)
    assert not any("post_grasp" in label for label in resumed_labels)


class FakeClient:
    def wait_for_service(self, timeout_sec: float) -> bool:
        return True


class FakeNode:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.client = FakeClient()
        self.state = SimpleNamespace(gripper_position=0)

    def service(self, command: str) -> str:
        self.events.append(command)
        return "0"

    def snapshot(self) -> list[float]:
        return [0.0] * 6

    def assert_gripper_ready(self) -> None:
        return None

    @staticmethod
    def state_joints(state: object) -> list[float]:
        return [0.0] * 6

    def destroy_node(self) -> None:
        return None


def patch_offline_runtime(
    monkeypatch: pytest.MonkeyPatch,
    node: FakeNode,
    events: list[str],
) -> None:
    monkeypatch.setattr(executor, "Executor", lambda: node)
    monkeypatch.setattr(executor.rclpy, "init", lambda **kwargs: None)
    monkeypatch.setattr(executor.rclpy, "ok", lambda: False)
    monkeypatch.setattr(executor, "validate_start_state", lambda unused: object())
    monkeypatch.setattr(
        executor,
        "build_tcp_route",
        lambda *args, **kwargs: ["offline-route"],
    )

    waypoint = SimpleNamespace(slot_code="GPU-01", label="pre_pick_safe_vertical", tcp=(0.0,) * 6)

    def preflight(*args, **kwargs):
        events.append("preflight")
        return [waypoint], {
            "waypoints": 1,
            "maximum_joint_step_deg": 1.0,
            "minimum_j6_deg": -1.0,
            "maximum_j6_deg": 1.0,
        }

    monkeypatch.setattr(executor, "preflight_route", preflight)


def test_execute_sets_global_speed_after_preflight_and_stops_on_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    node = FakeNode(events)
    patch_offline_runtime(monkeypatch, node, events)

    def fail_motion(unused_node: object, unused_waypoint: object) -> None:
        events.append("motion")
        raise RuntimeError("offline injected motion failure")

    monkeypatch.setattr(executor, "move_preflighted", fail_motion)
    args = SimpleNamespace(
        resume_held=False,
        run_record=tmp_path / "run.json",
        plan_file=tmp_path / "plan.json",
        stop_after_grasp=False,
    )
    payload = {
        "cycle_id": "test-cycle",
        "motion_profile": "smooth_combined_transfer_v1",
        "transfer_z_mm": 350.0,
        "speeds_percent": {
            "travel": 25,
            "combined_rotation": 25,
            "vertical": 10,
        },
    }

    with pytest.raises(RuntimeError, match="offline injected motion failure"):
        executor.execute(args, payload, [gpu_item()], "a" * 64)

    assert events == ["preflight", "SetSpeed(40)", "motion", "StopMotion()"]
    record = json.loads(args.run_record.read_text(encoding="utf-8"))
    assert record["plan_sha256"] == "a" * 64
    assert record["controller_global_speed_percent"] == 40
    assert record["stop_motion_on_error"]["succeeded"] is True
    assert record["stop_motion_on_error"]["response"] == "0"


def test_dry_run_never_sets_global_speed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    node = FakeNode(events)
    patch_offline_runtime(monkeypatch, node, events)
    args = SimpleNamespace()
    payload = {
        "transfer_z_mm": 350.0,
        "speeds_percent": {
            "travel": 25,
            "combined_rotation": 25,
            "vertical": 10,
        },
    }

    executor.dry_run(args, payload, [gpu_item()])

    assert "SetSpeed(40)" not in events
    assert "StopMotion()" not in events


def test_plan_sha_is_loaded_from_same_bytes_and_resume_rejects_mismatch(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "plan.json"
    raw = b'{"cycle_id":"test-cycle"}\n'
    plan_path.write_bytes(raw)
    payload, digest = executor.load_plan_json(plan_path)
    assert payload["cycle_id"] == "test-cycle"
    assert digest == hashlib.sha256(raw).hexdigest()

    run_record = tmp_path / "run.json"
    run_record.write_text(
        json.dumps(
            {
                "schema": executor.RUN_SCHEMA,
                "status": "paused_after_grasp_verification_required",
                "held_slot": "GPU-01",
                "cycle_id": "test-cycle",
                "plan_file": str(plan_path.resolve()),
                "plan_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        resume_held=True,
        run_record=run_record,
        plan_file=plan_path,
    )
    with pytest.raises(RuntimeError, match="SHA-256"):
        executor.execute(args, payload, [gpu_item()], digest)


def test_resume_held_accepts_start_slot_for_remaining_cycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "execute_full_fixed_cycle.py",
            "--start-slot",
            "GPU-01",
            "--resume-held",
            "--confirm-held-part",
            "--execute",
            "--confirm-cycle",
        ],
    )
    args = executor.parse_args()
    assert args.only_slot is None
    assert args.start_slot == "GPU-01"
    assert args.resume_held is True


def test_pm02_release_to_pm03_pick_stages_empty_wrist_transit_at_safe_z():
    item=gpu_item();item.update(slot_code='PM-03',part_type='long_orange')
    item['pick_final_tcp']=[-664.883,-66.964,-51.029,-180,0,91.747]
    start=[87.290,-517.486,190.862,-180,0,.854]
    route=executor.build_tcp_route([item],start,350,resume_after_grasp=False)
    before_pick=[]
    for _,w in route:
        before_pick.append(w)
        if w.label=='pick_combined_xy_abc':break
    assert [w.label for w in before_pick]==['pre_pick_safe_vertical',
        'pick_combined_xy_abc_midpoint','pick_combined_xy_abc_midpoint','pick_combined_xy_abc']
    assert all(w.tcp[2]==350 for w in before_pick)
    assert all(w.tcp[3:5]==(-180,0) for w in before_pick)
    assert before_pick[-1].tcp[:2]==tuple(item['pick_final_tcp'][:2])
    assert before_pick[1].tcp[5]<before_pick[2].tcp[5]<before_pick[3].tcp[5]


def test_place_review_stops_before_descent_release_and_retreat(tmp_path, monkeypatch):
    events = []
    node = FakeNode(events)
    patch_offline_runtime(monkeypatch, node, events)
    node.gripper = lambda position, label: events.append(('gripper', position))
    monkeypatch.setattr(executor, 'read_gripper_current_percent', lambda n: 10)
    labels = ['pick_final_50mm_vertical', 'place_approach_50mm_vertical',
              'place_final_50mm_vertical', 'post_release_lift_100mm_vertical']
    checked = [SimpleNamespace(slot_code='GPU-01', label=label, tcp=(0.0,) * 6) for label in labels]
    monkeypatch.setattr(executor, 'preflight_route', lambda *a, **kw: (checked,
        dict(waypoints=4, maximum_joint_step_deg=1, minimum_j6_deg=0, maximum_j6_deg=1)))
    def move(n, w):
        events.append(w.label)
        return list(w.tcp)
    monkeypatch.setattr(executor, 'move_preflighted', move)
    args = SimpleNamespace(resume_held=False, run_record=tmp_path/'run.json',
        plan_file=tmp_path/'plan.json', stop_after_grasp=False, stop_before_place=True)
    payload = dict(cycle_id='review', motion_profile='smooth_combined_transfer_v1',
                   transfer_z_mm=350, speeds_percent=dict(travel=25, combined_rotation=25, vertical=10))
    executor.execute(args, payload, [gpu_item()], 'a'*64)
    assert 'place_final_50mm_vertical' not in events
    assert 'post_release_lift_100mm_vertical' not in events
    assert ('gripper', 70) not in events
    assert 'StopMotion()' not in events
    record = json.loads(args.run_record.read_text())
    assert record['status'] == 'paused_before_place_visual_confirmation_required'
    assert record['held_slot'] == 'GPU-01'
    assert record['part_held_candidate'] is True
    assert record['motion_completed_slots'] == []


def test_hover_only_plan_cannot_enter_normal_execution(monkeypatch):
    monkeypatch.setattr(executor.rclpy, 'init', lambda: pytest.fail('must reject before ROS access'))
    with pytest.raises(RuntimeError, match='review plan forbids final placement'):
        executor.execute(SimpleNamespace(stop_before_place=False),
                         {'execution_scope': 'placement_review_hover_only'}, [], 'unused')

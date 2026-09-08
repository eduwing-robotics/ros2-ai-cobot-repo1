from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "vision_assembly" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from full_cycle_plan import (  # noqa: E402
    ALIGN_CARRIED_AXIS_MODE,
    MOTION_PROFILE,
    PRESERVE_PICK_TCP_MODE,
    SLOT_SEQUENCE,
    build_plan,
)
from placement_orientation import tool_axis_base_angle_deg  # noqa: E402


SNAPSHOT_PATH = (
    ROOT
    / "vision_assembly"
    / "data"
    / "fixed_cycle_full_restart_retry2_2026-09-02.json"
)
RECIPES_PATH = ROOT / "vision_assembly" / "config" / "part_gripper_recipes.json"
SLOTS_PATH = ROOT / "vision_assembly" / "config" / "assembly_slots_r1.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def planned_cycle() -> tuple[dict, dict]:
    recipes = copy.deepcopy(load(RECIPES_PATH))
    plan = build_plan(
        load(SNAPSHOT_PATH),
        recipes,
        load(SLOTS_PATH),
        snapshot_path=SNAPSHOT_PATH,
        created_unix=1_788_400_000.0,
    )
    return plan, recipes


def by_slot(plan: dict, slot_code: str) -> dict:
    return next(item for item in plan["plan"] if item["slot_code"] == slot_code)


def test_explicit_remaining_selection_preserves_physical_numbers():
    snapshot = copy.deepcopy(load(SNAPSHOT_PATH))
    selected = [s for s in SLOT_SEQUENCE if not s.startswith(('GPU-', 'CAP-')) and not s.endswith('-01')]
    snapshot['authorized_selected_slots'] = selected
    snapshot['tray_capture']['parts'] = [p for p in snapshot['tray_capture']['parts']
        if p['part_type'] in ('hbm','long_orange','black_block','marked_white') and p['instance_index'] > 1]
    plan = build_plan(snapshot, load(RECIPES_PATH), load(SLOTS_PATH), selected_slots=selected)
    assert len(plan['plan']) == 15
    assert plan['plan_selection']['mode'] == 'explicit_slots'
    for item in plan['plan']:
        assert item['tray_instance_index'] == int(item['slot_code'].split('-')[1])
    with pytest.raises(RuntimeError, match='scope'):
        build_plan(snapshot, load(RECIPES_PATH), load(SLOTS_PATH), selected_slots=selected[:-1])
    with pytest.raises(RuntimeError, match='non-SMD'):
        build_plan(snapshot, load(RECIPES_PATH), load(SLOTS_PATH), selected_slots=['CAP-02'])
    with pytest.raises(RuntimeError, match='unique'):
        build_plan(snapshot, load(RECIPES_PATH), load(SLOTS_PATH), selected_slots=['HBM-02','HBM-02'])


def modulo_axis_error(first_deg: float, second_deg: float, period_deg: float) -> float:
    return abs((first_deg - second_deg + period_deg / 2.0) % period_deg - period_deg / 2.0)


@pytest.mark.parametrize('kind', ['gpu','hbm','long_orange','black_block','marked_white','right_white_brown'])
def test_fixed_fixture_pick_height_does_not_follow_depth_noise(kind):
    from full_cycle_plan import _pick_z
    recipe=load(RECIPES_PATH)['parts'][kind]
    expected=recipe['grasp_height']['taught_tcp_z_mm']
    for surface in (-48.,-43.,-40.):
        assert _pick_z(recipe,surface,kind)==(expected,'fixed_fixture_absolute')


def test_remaining14_excludes_released_hbm02():
    snapshot=copy.deepcopy(load(SNAPSHOT_PATH))
    selected=[s for s in SLOT_SEQUENCE if not s.startswith(('GPU-','CAP-')) and not s.endswith('-01') and s!='HBM-02']
    snapshot['authorized_selected_slots']=selected
    snapshot['tray_capture']['parts']=[p for p in snapshot['tray_capture']['parts']
        if p['part_type'] in ('hbm','long_orange','black_block','marked_white')
        and p['instance_index'] > (2 if p['part_type']=='hbm' else 1)]
    plan=build_plan(snapshot,load(RECIPES_PATH),load(SLOTS_PATH),selected_slots=selected)
    assert [p['slot_code'] for p in plan['plan']]==selected
    assert len(plan['plan'])==14


def test_builds_exact_25_part_sequence(planned_cycle: tuple[dict, dict]) -> None:
    plan, _ = planned_cycle

    assert plan["schema"] == "fr5.full_fixed_cycle_plan/v1"
    assert plan["motion_profile"] == MOTION_PROFILE
    assert plan["robot_motion_authorized"] is False
    assert plan["status"] == "planned_not_executed"
    assert len(plan["plan"]) == 25
    assert tuple(item["slot_code"] for item in plan["plan"]) == SLOT_SEQUENCE
    assert [item["part_type"] for item in plan["plan"]] == (
        ["gpu"]
        + ["hbm"] * 8
        + ["long_orange"] * 4
        + ["black_block"] * 5
        + ["marked_white"] * 2
        + ["right_white_brown"] * 5
    )


def test_hbm_aligns_carried_axis_to_slot_with_required_rotation(
    planned_cycle: tuple[dict, dict],
) -> None:
    plan, _ = planned_cycle
    hbm_items = [item for item in plan["plan"] if item["part_type"] == "hbm"]

    assert len(hbm_items) == 8
    for item in hbm_items:
        assert 80.0 < item["pick_final_tcp"][5] < 100.0
        assert abs(item["place_final_tcp"][5]) > 170.0
        orientation = item["placement_orientation"]
        planned = orientation["planned_from_pick"]
        assert orientation["mode"] == ALIGN_CARRIED_AXIS_MODE
        assert abs(orientation["rotation_delta_deg"]) > 80.0
        assert orientation["rotation_skipped_in_plan"] is False
        assert orientation["rotation_delta_deg"] == pytest.approx(
            planned["rotation_delta_deg"]
        )
        assert item["place_final_tcp"][3:] == pytest.approx(
            planned["target_tcp_abc_deg"]
        )
        assert item["place_final_tcp"][3:] != pytest.approx(
            item["pick_final_tcp"][3:]
        )
        placed_axis = tool_axis_base_angle_deg(
            item["place_final_tcp"][3:], orientation["gripper_axis"]
        )
        assert modulo_axis_error(
            placed_axis,
            orientation["target_axis_base_deg"],
            orientation["symmetry_period_deg"],
        ) < 1e-6


def test_gpu_and_vrm_keep_carried_axis_alignment(
    planned_cycle: tuple[dict, dict],
) -> None:
    plan, _ = planned_cycle
    aligned_items = [by_slot(plan, "GPU-01")] + [
        by_slot(plan, f"VRM-{index:02d}") for index in range(1, 6)
    ]

    assert abs(aligned_items[0]["placement_orientation"]["rotation_delta_deg"]) > 80.0
    assert any(
        abs(item["placement_orientation"]["rotation_delta_deg"]) > 80.0
        for item in aligned_items[1:]
    )
    for item in aligned_items:
        orientation = item["placement_orientation"]
        planned = orientation["planned_from_pick"]
        assert orientation["mode"] == ALIGN_CARRIED_AXIS_MODE
        assert item["place_final_tcp"][3:] == pytest.approx(
            planned["target_tcp_abc_deg"]
        )
        placed_axis = tool_axis_base_angle_deg(
            item["place_final_tcp"][3:], orientation["gripper_axis"]
        )
        assert modulo_axis_error(
            placed_axis,
            orientation["target_axis_base_deg"],
            orientation["symmetry_period_deg"],
        ) < 1e-6


def test_pick_z_grippers_and_pm_rotated_correction_are_preserved(
    planned_cycle: tuple[dict, dict],
) -> None:
    plan, recipes_config = planned_cycle
    recipes = recipes_config["parts"]

    expected_grippers = {
        "GPU-01": (70, 65, 70),
        "HBM-01": (25, 18, 25),
        "PM-01": (30, 25, 30),
        "VRM-01": (30, 24, 28),
        "IND-01": (21, 14, 20),
        "CAP-01": (18, 12, 17),
    }
    for slot_code, expected in expected_grippers.items():
        item = by_slot(plan, slot_code)
        assert (
            item["tray_open_position"],
            item["grip_position"],
            item["release_position"],
        ) == expected

    gpu = by_slot(plan, "GPU-01")
    assert gpu["pick_z_mode"] == "fixed_fixture_absolute"
    assert gpu["pick_final_tcp"][2] == pytest.approx(
        -49.719
    )

    hbm = by_slot(plan, "HBM-01")
    assert hbm["pick_final_tcp"][2] == pytest.approx(
        recipes["hbm"]["grasp_height"]["taught_tcp_z_mm"]
    )

    vrm = by_slot(plan, "VRM-01")
    assert vrm["pick_final_tcp"][2] == pytest.approx(
        recipes["black_block"]["grasp_height"]["taught_tcp_z_mm"]
    )

    capacitor = by_slot(plan, "CAP-01")
    assert capacitor["pick_z_mode"] == "fixed_fixture_absolute"
    assert capacitor["pick_final_tcp"][2] == pytest.approx(
        recipes["right_white_brown"]["grasp_height"]["taught_tcp_z_mm"]
    )

    pm_recipe = recipes["long_orange"]
    tool_xy = pm_recipe["grasp_center_correction_tool_mm"]
    extra_xy = pm_recipe["operator_additional_correction_base_mm"]
    for index in range(1, 5):
        item = by_slot(plan, f"PM-{index:02d}")
        rotated = Rotation.from_euler(
            "xyz", item["pick_final_tcp"][3:], degrees=True
        ).as_matrix() @ np.array([tool_xy["x"], tool_xy["y"], 0.0])
        expected = rotated[:2] + np.array([extra_xy["x"], extra_xy["y"]])
        assert item["pick_correction_base_mm"] == pytest.approx(expected.tolist())


def test_preserve_policy_is_rejected_for_non_hbm() -> None:
    recipes = copy.deepcopy(load(RECIPES_PATH))
    recipes["parts"]["gpu"]["placement_orientation_policy"][
        "mode"
    ] = PRESERVE_PICK_TCP_MODE

    with pytest.raises(RuntimeError, match="only valid for HBM"):
        build_plan(load(SNAPSHOT_PATH), recipes, load(SLOTS_PATH))


def test_gpu_only_plan_allows_board_and_tray_without_smd_close() -> None:
    recipes = copy.deepcopy(load(RECIPES_PATH))
    snapshot = copy.deepcopy(load(SNAPSHOT_PATH))
    snapshot["board_captured"] = True
    snapshot["tray_captured"] = True
    snapshot["smd_close_captured"] = False
    snapshot["ready_for_continuous_execution"] = False

    plan = build_plan(
        snapshot,
        recipes,
        load(SLOTS_PATH),
        created_unix=1_788_400_000.0,
        only_slot="GPU-01",
    )

    assert [item["slot_code"] for item in plan["plan"]] == ["GPU-01"]
    assert plan["plan_selection"] == {
        "mode": "single_slot",
        "requested_only_slot": "GPU-01",
        "selected_slots": ["GPU-01"],
    }


def test_full_plan_still_requires_continuous_readiness() -> None:
    snapshot = copy.deepcopy(load(SNAPSHOT_PATH))
    snapshot["ready_for_continuous_execution"] = False

    with pytest.raises(RuntimeError, match="not ready for continuous execution"):
        build_plan(snapshot, load(RECIPES_PATH), load(SLOTS_PATH))


def test_partial_planning_is_restricted_to_supported_first_slots() -> None:
    with pytest.raises(RuntimeError, match="restricted to GPU-01 or HBM-01"):
        build_plan(
            load(SNAPSHOT_PATH),
            load(RECIPES_PATH),
            load(SLOTS_PATH),
            only_slot="HBM-02",
        )


def test_executor_requires_cli_and_metadata_for_single_slot_plan() -> None:
    executor = pytest.importorskip("execute_full_fixed_cycle")
    snapshot = copy.deepcopy(load(SNAPSHOT_PATH))
    snapshot.update(
        board_captured=True,
        tray_captured=True,
        smd_close_captured=False,
        ready_for_continuous_execution=False,
    )
    plan = build_plan(
        snapshot,
        load(RECIPES_PATH),
        load(SLOTS_PATH),
        created_unix=time.time(),
        only_slot="GPU-01",
    )

    items = executor.validate_plan(
        plan, 1800.0, requested_only_slot="GPU-01"
    )
    assert executor.select_items(items, "GPU-01", None, None) == items

    with pytest.raises(RuntimeError, match="requires matching CLI"):
        executor.validate_plan(plan, 1800.0)
    with pytest.raises(RuntimeError, match="does not match CLI"):
        executor.validate_plan(plan, 1800.0, requested_only_slot="HBM-01")

    bad_metadata = copy.deepcopy(plan)
    bad_metadata["plan_selection"]["mode"] = "full_cycle"
    with pytest.raises(RuntimeError, match="selection metadata is invalid"):
        executor.validate_plan(
            bad_metadata, 1800.0, requested_only_slot="GPU-01"
        )


def test_hbm_01_single_slot_plan_aligns_and_executor_rejects_fake_zero_rotation() -> None:
    executor = pytest.importorskip("execute_full_fixed_cycle")
    snapshot = copy.deepcopy(load(SNAPSHOT_PATH))
    hbm_01 = next(
        item
        for item in snapshot["tray_capture"]["parts"]
        if item["part_type"] == "hbm" and item["instance_index"] == 1
    )
    snapshot["tray_capture"]["parts"] = [hbm_01]
    snapshot["tray_capture"]["counts"] = {"hbm": 1}
    snapshot["tray_capture"]["part_count"] = 1
    snapshot["tray_capture"]["capture_scope"] = {
        "mode": "part_instance_subset",
        "selected_part_types": ["hbm"],
        "selected_instance_index": 1,
    }
    snapshot.update(
        board_captured=True,
        tray_captured=True,
        smd_close_captured=False,
        ready_for_continuous_execution=False,
    )

    plan = build_plan(
        snapshot,
        load(RECIPES_PATH),
        load(SLOTS_PATH),
        created_unix=time.time(),
        only_slot="HBM-01",
    )

    assert [item["slot_code"] for item in plan["plan"]] == ["HBM-01"]
    hbm = plan["plan"][0]
    orientation = hbm["placement_orientation"]
    assert hbm["tray_instance_index"] == 1
    assert orientation["mode"] == ALIGN_CARRIED_AXIS_MODE
    assert abs(orientation["rotation_delta_deg"]) > 80.0
    assert orientation["rotation_skipped_in_plan"] is False
    assert hbm["place_final_tcp"][3:] == pytest.approx(
        orientation["planned_from_pick"]["target_tcp_abc_deg"]
    )
    executor.validate_plan(plan, 1800.0, requested_only_slot="HBM-01")

    fake_zero = copy.deepcopy(plan)
    fake_hbm = fake_zero["plan"][0]
    fake_hbm["place_final_tcp"][3:] = fake_hbm["pick_final_tcp"][3:]
    fake_orientation = fake_hbm["placement_orientation"]
    fake_orientation["rotation_delta_deg"] = 0.0
    fake_orientation["planned_from_pick"]["rotation_delta_deg"] = 0.0
    with pytest.raises(RuntimeError, match="successful gripper direction"):
        executor.validate_plan(
            fake_zero, 1800.0, requested_only_slot="HBM-01"
        )

    preserve = copy.deepcopy(plan)
    preserve["plan"][0]["placement_orientation"]["mode"] = PRESERVE_PICK_TCP_MODE
    with pytest.raises(RuntimeError, match="must align the carried HBM axis"):
        executor.validate_plan(
            preserve, 1800.0, requested_only_slot="HBM-01"
        )

    assert plan["plan_selection"] == {
        "mode": "single_slot",
        "requested_only_slot": "HBM-01",
        "selected_slots": ["HBM-01"],
    }


def test_common_board_place_z_raise_is_applied_to_every_slot(
    planned_cycle: tuple[dict, dict],
) -> None:
    plan, _ = planned_cycle
    snapshot = load(SNAPSHOT_PATH)

    assert plan["board_place_common_z_raise_mm"] == pytest.approx(0.3)
    for item in plan["plan"]:
        calibrated_z = snapshot["resolved_placements"][item["slot_code"]][
            "final_tcp_z_mm"
        ]
        assert item["calibrated_place_final_tcp_z_mm"] == pytest.approx(calibrated_z)
        assert item["board_place_common_z_raise_mm"] == pytest.approx(0.3)
        assert item["place_final_tcp"][2] == pytest.approx(calibrated_z + ((-1.4 if item["slot_code"] == "CAP-01" else -2.1) if item["part_type"] == "right_white_brown" else -0.7 if item["part_type"] == "hbm" else -0.2 if item["part_type"] == "long_orange" else 0.3))


def test_smd_plan_exposes_existing_correction_without_claiming_alignment(planned_cycle):
    plan, _ = planned_cycle
    smds = [item for item in plan['plan'] if item['part_type'] == 'right_white_brown']
    assert len(smds) == 5
    for item in smds:
        audit = item['grasp_center_diagnostic']
        assert audit['fixed_base_correction_xy_mm'] == [-2.089, 2.779]
        assert audit['expected_tcp_base_xy_mm'] == pytest.approx(item['pick_final_tcp'][:2])
        assert audit['arithmetic_consistent'] is True
        assert audit['physical_alignment_verified'] is False
        assert audit['measured_remaining_error_xy_mm'] is None


def test_pm01_keeps_taught_pick_and_place_branches(planned_cycle):
    plan, _ = planned_cycle
    pm = by_slot(plan, "PM-01")
    assert 80.0 < pm["pick_final_tcp"][5] < 100.0
    assert abs(pm["place_final_tcp"][5]) > 170.0
    # Keep the downstream PM-02 grasp on its original branch as well.
    assert 80.0 < by_slot(plan, "PM-02")["pick_final_tcp"][5] < 100.0
    assert abs(pm["placement_orientation"]["rotation_delta_deg"]) <= 95.0


def test_inductor_successful_positive_staged_transfer(planned_cycle):
    executor = pytest.importorskip("execute_full_fixed_cycle")
    plan, _ = planned_cycle
    for code in ("IND-01", "IND-02"):
        item = by_slot(plan, code)
        assert abs(item["pick_final_tcp"][5]) < 5.0
        assert abs(item["place_final_tcp"][5]) > 175.0
        route = executor.build_tcp_route([item], item["pick_final_tcp"], 350.0,
                                         resume_after_grasp=False)
        steps = [w for _, w in route]
        start = next(i for i, w in enumerate(steps) if w.label == "carry_safe_vertical")
        end = next(i for i, w in enumerate(steps) if w.label == "place_combined_xy_abc")
        for a, b in zip(steps[start:end], steps[start+1:end+1]):
            assert a.tcp[2] == b.tcp[2] == 350.0
            assert 0.0 < (b.tcp[5] - a.tcp[5]) % 360.0 <= 60.0 + 1e-6
            assert modulo_axis_error(a.tcp[3], b.tcp[3], 360.0) < 1e-6


@pytest.mark.parametrize('start_c', [90.0, -179.25])
def test_inductor_first_pick_stages_wrist_from_home_or_vrm(planned_cycle, start_c):
    executor = pytest.importorskip('execute_full_fixed_cycle')
    item = by_slot(planned_cycle[0], 'IND-01')
    start = [-527.997, -60.954, 337.88, 180.0, 0.0, start_c]
    route = executor.build_tcp_route([item], start, 350.0, resume_after_grasp=False)
    index = next(i for i, (_, w) in enumerate(route) if w.label == 'pick_combined_xy_abc')
    assert index == 3
    for (_, a), (_, b) in zip(route[:index], route[1:index+1]):
        delta = (b.tcp[5] - a.tcp[5] + 180) % 360 - 180
        assert -61 < delta < 0
        assert a.tcp[2] == b.tcp[2] == 350.0
        assert modulo_axis_error(a.tcp[3], b.tcp[3], 360.0) < 1e-6


def test_inductor_return_unwinds_wrist_at_transfer_height(planned_cycle):
    executor = pytest.importorskip("execute_full_fixed_cycle")
    plan, _ = planned_cycle
    first, second = (by_slot(plan, code) for code in ("IND-01", "IND-02"))
    route = executor.build_tcp_route([first, second], first["pick_final_tcp"],
                                     350.0, resume_after_grasp=False)
    steps = [w for code, w in route if code == "IND-02"]
    end = next(i for i, w in enumerate(steps) if w.label == "pick_combined_xy_abc")
    for a, b in zip(steps[:end], steps[1:end+1]):
        delta = (b.tcp[5] - a.tcp[5] + 180.0) % 360.0 - 180.0
        assert -61.0 < delta < 0.0
        assert a.tcp[2] == b.tcp[2] == 350.0


@pytest.mark.parametrize("phase,count", [("non-smd",20),("smd",5)])
def test_separate_phases_preserve_order_and_scope(phase,count):
    executor = pytest.importorskip("execute_full_fixed_cycle")
    snapshot=copy.deepcopy(load(SNAPSHOT_PATH))
    snapshot["ready_for_continuous_execution"]=False
    snapshot["smd_close_captured"]=(phase=="smd")
    plan=build_plan(snapshot,load(RECIPES_PATH),load(SLOTS_PATH),phase=phase)
    assert len(plan["plan"])==count
    assert plan["plan_selection"]["mode"]==phase
    executor.validate_plan(plan,1800.0)
    if phase=="non-smd":
        assert plan["plan"][0]["slot_code"]=="GPU-01"
        assert plan["plan"][-1]["slot_code"]=="IND-02"
    else:
        assert plan["plan"][0]["slot_code"]=="CAP-01"
        snapshot["smd_close_captured"]=False
        with pytest.raises(RuntimeError,match="SMDView"):
            build_plan(snapshot,load(RECIPES_PATH),load(SLOTS_PATH),phase=phase)



def test_non_smd_inspection_reference_is_serializable_and_gpu_can_pause():
    executor=pytest.importorskip("execute_full_fixed_cycle")
    snapshot=copy.deepcopy(load(SNAPSHOT_PATH))
    for i,p in enumerate(snapshot["tray_capture"]["parts"]):
        p["reference_center_pixel"]=[100.0+i,200.0]
    plan=build_plan(snapshot,load(RECIPES_PATH),load(SLOTS_PATH),phase="non-smd")
    plan=json.loads(json.dumps(plan))
    reference=plan["tray_inspection_reference"]
    assert len(reference["bindings"])==20
    items=executor.validate_plan(plan,1800,requested_only_slot="GPU-01")
    assert [i["slot_code"] for i in executor.select_items(items,"GPU-01",None,None)]==["GPU-01"]


@pytest.mark.parametrize("slot_index", range(1, 6))
def test_vrm_locks_success_branch_even_when_opposite_is_shorter(slot_index):
    from full_cycle_plan import _plan_placement_orientation
    recipes = load(RECIPES_PATH)["parts"]
    policy = recipes["black_block"]["placement_orientation_policy"]
    # September 5 regression: -86.524 was shorter than successful +93.476.
    board = Rotation.from_euler("z", 0.563, degrees=True).as_matrix()
    place, metadata = _plan_placement_orientation(
        slot_code=f"VRM-{slot_index:02d}", part_type="black_block", policy=policy,
        slot={"long_axis_board_deg": 90.0, "preferred_tcp_c_deg": 0.0},
        board_rotation=board, pick_abc=[-180.0, 0.0, 87.087],
    )
    assert abs(place[2]) > 179.0
    assert metadata["rotation_delta_deg"] == pytest.approx(93.476)


def test_vrm_rejects_locked_branch_outside_envelope_without_fallback():
    from full_cycle_plan import _plan_placement_orientation
    policy = load(RECIPES_PATH)["parts"]["black_block"]["placement_orientation_policy"]
    with pytest.raises(RuntimeError, match="exceeds"):
        _plan_placement_orientation(
            slot_code="VRM-03", part_type="black_block", policy=policy,
            slot={"long_axis_board_deg": 90.0, "preferred_tcp_c_deg": 180.0},
            board_rotation=np.eye(3), pick_abc=[-180.0, 0.0, 59.0],
        )


def test_executor_rejects_opposite_vrm_branch(planned_cycle):
    executor = pytest.importorskip("execute_full_fixed_cycle")
    plan = copy.deepcopy(planned_cycle[0])
    plan["created_unix"] = time.time()
    executor.validate_plan(plan, 1800.0)
    vrm = by_slot(plan, "VRM-03")
    # Forge an otherwise aligned opposite branch including coherent metadata.
    from placement_orientation import plan_carried_part_orientation
    policy = vrm["placement_orientation"]
    opposite = plan_carried_part_orientation(
        vrm["pick_final_tcp"][3:], policy["target_axis_base_deg"],
        policy["gripper_axis"], policy["symmetry_period_deg"],
        preferred_tcp_c_deg=0.0, lock_preferred_branch=True,
    )
    vrm["place_final_tcp"][3:] = opposite["target_tcp_abc_deg"]
    policy["planned_from_pick"] = opposite
    policy["rotation_delta_deg"] = opposite["rotation_delta_deg"]
    policy["rotation_skipped_in_plan"] = False
    with pytest.raises(RuntimeError, match="successful gripper direction"):
        executor.validate_plan(plan, 1800.0)


def test_smd_preserves_operator_confirmed_near_zero_pick_branch():
    snapshot = load(SNAPSHOT_PATH)
    snapshot['smd_close_captured'] = True
    angles = [0.897, -6.813, -4.270, -4.238, -0.854]
    for part in snapshot['tray_capture']['parts']:
        if part['part_type'] == 'right_white_brown':
            part['long_axis_angle_base_deg'] = angles[part['instance_index']-1]
    plan = build_plan(snapshot, load(RECIPES_PATH), load(SLOTS_PATH), phase='smd')
    for item, angle in zip(plan['plan'], angles):
        assert item['pick_final_tcp'][5] == pytest.approx(angle)
        assert [item[k] for k in ['tray_open_position','grip_position','release_position']] == [18,12,17]


@pytest.mark.parametrize('slot', SLOT_SEQUENCE)
@pytest.mark.parametrize('field', ['pick_final_tcp', 'place_final_tcp'])
def test_executor_rejects_opposite_direction_for_every_part(planned_cycle, slot, field):
    executor = pytest.importorskip('execute_full_fixed_cycle')
    plan = copy.deepcopy(planned_cycle[0])
    plan['created_unix'] = time.time()
    item = by_slot(plan, slot)
    item[field][5] = (item[field][5]+360) % 360-180
    with pytest.raises(RuntimeError, match='successful gripper direction'):
        executor.validate_plan(plan, 1800)


def test_successful_smd_place_directions_are_independently_locked(planned_cycle):
    from successful_gripper_directions import distance
    for i in range(1,6):
        item = by_slot(planned_cycle[0], f'CAP-{i:02d}')
        assert distance(item['pick_final_tcp'][5], 0) < 15
        assert distance(item['place_final_tcp'][5], 180 if i==1 else 90) < 15


@pytest.mark.parametrize("pick_c", [84.467, 75.0])
def test_vrm_total_rotation_uses_staged_successful_branch_envelope(pick_c):
    from full_cycle_plan import _plan_placement_orientation
    from full_cycle_motion import DEFAULT_MAX_JOINT_STEP_DEG
    policy = load(RECIPES_PATH)["parts"]["black_block"]["placement_orientation_policy"]
    place, metadata = _plan_placement_orientation(
        slot_code="VRM-01", part_type="black_block", policy=policy,
        slot={"long_axis_board_deg": 90.0}, board_rotation=np.eye(3),
        pick_abc=[-180.0, 0.0, pick_c])
    assert abs(place[2]) == pytest.approx(180)
    assert metadata["rotation_delta_deg"] == pytest.approx(180-pick_c)
    assert metadata["maximum_intentional_rotation_deg"] == 120
    assert DEFAULT_MAX_JOINT_STEP_DEG == 95


def test_pm02_uses_operator_corrected_camera_facing_branch(planned_cycle):
    from successful_gripper_directions import distance
    item=by_slot(planned_cycle[0], 'PM-02')
    assert distance(item['pick_final_tcp'][5],90)<15
    assert distance(item['place_final_tcp'][5],180)<15

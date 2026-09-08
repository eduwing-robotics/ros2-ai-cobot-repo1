from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


from safe_part_pick import load_pick_recipe, resolve_grasp_final_z


def test_smd_pick_recipe_uses_saved_absolute_z_and_directed_branch():
    recipe = load_pick_recipe("right_white_brown")
    assert recipe["grasp_z_mode"] == "fixed_fixture_absolute"
    assert recipe["grasp_fixed_tcp_z_mm"] == -52.177
    assert resolve_grasp_final_z(recipe, -45.0) == -52.177
    assert resolve_grasp_final_z(recipe, -49.0) == -52.177
    assert recipe["gripper_axis"] == "tool_x"
    assert recipe["symmetric_rotation_branch"] == "negative"
    assert recipe["max_pick_rotation_deg"] == 105.0


def test_smd_tray_open_and_board_release_are_independent():
    recipe = load_pick_recipe("right_white_brown")
    assert recipe["base_correction_xy_mm"] == [-2.089, 2.779]
    assert recipe["tray_open_args"][1] == 18
    assert recipe["grip_args"][1] == 12
    assert recipe["release_args"][1] == 17


def test_vrm_recipe_loads_saved_center_and_fixed_fixture_height():
    recipe = load_pick_recipe("black_block")
    # 2026-09-07 four-edge validation superseded the old [-1.492, 0.09]
    # correction. The production planner tests validate that measurement path;
    # loading this helper's legacy angle field is not a physical pick approval.
    assert recipe["base_correction_xy_mm"] == [-1.5164288635806775, 1.5898010636828328]
    assert recipe["grasp_axis_offset_deg"] == -4.5
    assert recipe["grasp_z_mode"] == "fixed_fixture_absolute"
    assert recipe["grasp_z_offset_mm"] is None
    assert resolve_grasp_final_z(recipe, -45.306) == -53.238
    assert resolve_grasp_final_z(recipe, -48.0) == -53.238
    assert recipe["grip_args"][1] == 24


def test_inductor_pick_recipe_uses_operator_validated_center_and_grip():
    recipe = load_pick_recipe("marked_white")
    assert recipe["base_correction_xy_mm"] == [0.746, 3.515]
    assert recipe["grasp_z_mode"] == "fixed_fixture_absolute"
    assert recipe["grasp_z_offset_mm"] is None
    assert resolve_grasp_final_z(recipe, -43.144) == -51.194
    assert resolve_grasp_final_z(recipe, -47.0) == -51.194
    assert recipe["grip_args"][1] == 14

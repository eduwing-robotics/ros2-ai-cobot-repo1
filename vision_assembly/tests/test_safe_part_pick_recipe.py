from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


from safe_part_pick import load_pick_recipe, resolve_grasp_final_z


def test_smd_pick_recipe_uses_saved_absolute_z_and_directed_branch():
    recipe = load_pick_recipe("right_white_brown")
    assert recipe["grasp_z_mode"] == "fixed_fixture_absolute"
    assert recipe["grasp_fixed_tcp_z_mm"] == -53.153
    assert resolve_grasp_final_z(recipe, -45.0) == -53.153
    assert resolve_grasp_final_z(recipe, -49.0) == -53.153
    assert recipe["gripper_axis"] == "tool_x"
    assert recipe["symmetric_rotation_branch"] == "negative"
    assert recipe["max_pick_rotation_deg"] == 95.0


def test_smd_tray_open_and_board_release_are_independent():
    recipe = load_pick_recipe("right_white_brown")
    assert recipe["tray_open_args"][1] == 18
    assert recipe["grip_args"][1] == 12
    assert recipe["release_args"][1] == 17

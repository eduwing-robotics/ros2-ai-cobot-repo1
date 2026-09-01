from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_demo_launch


def generate_launch_description():
    # generate_demo_launch() includes rsp.launch.py, which is what actually
    # publishes /robot_description (and from there ros2_control_node picks up
    # its hardware plugin). Setting use_fake_hardware here, before that include
    # runs, is what actually reaches it — this file's own MoveItConfigsBuilder
    # call below only affects move_group's copy, not ros2_control's.
    declare_use_fake_hardware = DeclareLaunchArgument(
        "use_fake_hardware", default_value="false"
    )

    moveit_config = MoveItConfigsBuilder(
        "fairino5_v6_robot", package_name="fairino5_v6_moveit2_config"
    ).to_moveit_configs()

    ld = LaunchDescription()
    ld.add_action(declare_use_fake_hardware)
    for action in generate_demo_launch(moveit_config).entities:
        ld.add_action(action)
    return ld

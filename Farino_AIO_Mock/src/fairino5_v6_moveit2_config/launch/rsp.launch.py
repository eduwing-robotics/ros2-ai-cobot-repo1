from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from moveit_configs_utils import MoveItConfigsBuilder
from moveit_configs_utils.launches import generate_rsp_launch


def generate_launch_description():
    # use_fake_hardware defaults to true so demo.launch.py (which includes this
    # file without setting the argument) stays simulation-only. real_robot.launch.py
    # sets it to false before this file is included, which this Declare picks up
    # instead of overriding (ROS2 launch resolves LaunchConfiguration by name
    # across the whole launch tree; a later DeclareLaunchArgument with the same
    # name only supplies a fallback default, it does not override an existing value).
    declare_use_fake_hardware = DeclareLaunchArgument(
        "use_fake_hardware", default_value="true"
    )

    moveit_config = (
        MoveItConfigsBuilder(
            "fairino5_v6_robot", package_name="fairino5_v6_moveit2_config"
        )
        .robot_description(
            mappings={"use_fake_hardware": LaunchConfiguration("use_fake_hardware")}
        )
        .to_moveit_configs()
    )

    ld = LaunchDescription()
    ld.add_action(declare_use_fake_hardware)
    for action in generate_rsp_launch(moveit_config).entities:
        ld.add_action(action)
    return ld

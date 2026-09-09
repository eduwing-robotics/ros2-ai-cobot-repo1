from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
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
    ld.add_action(SetEnvironmentVariable("ROS_DOMAIN_ID", "5"))
    ld.add_action(declare_use_fake_hardware)
    ld.add_action(DeclareLaunchArgument("start_sequencer", default_value="false"))
    for action in generate_demo_launch(moveit_config).entities:
        ld.add_action(action)
    ld.add_action(GroupAction(
        condition=IfCondition(LaunchConfiguration("start_sequencer")),
        scoped=True,
        actions=[
            SetEnvironmentVariable("ASSEMBLY_SEQUENCER_MODE", "real"),
            DeclareLaunchArgument("start_endpoint", default_value="true"),
            DeclareLaunchArgument("endpoint_ip", default_value="0.0.0.0"),
            DeclareLaunchArgument("endpoint_port", default_value="10000"),
            Node(
                package="ros_tcp_endpoint",
                executable="default_server_endpoint",
                name="UnityEndpoint",
                output="screen",
                condition=IfCondition(LaunchConfiguration("start_endpoint")),
                parameters=[{
                    "ROS_IP": LaunchConfiguration("endpoint_ip"),
                    "ROS_TCP_PORT": ParameterValue(
                        LaunchConfiguration("endpoint_port"), value_type=int
                    ),
                }],
            ),
            Node(
                package="assembly_sequencer",
                executable="sequencer_node",
                name="assembly_sequencer_real",
                output="screen",
            ),
        ],
    ))
    return ld

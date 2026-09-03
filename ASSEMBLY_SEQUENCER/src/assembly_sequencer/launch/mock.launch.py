"""Run the Mock robot backend behind the AssemblySequencer process."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    existing_package = get_package_share_directory("fairino5_v6_moveit2_config")
    package_share = get_package_share_directory("assembly_sequencer")

    mock_node = Node(
        package="fairino5_v6_moveit2_config",
        executable="mock_sim.py",
        name="mock_movej",
        output="screen",
        arguments=[
            "--listen-unity", "--velocity", "100", "--acceleration", "100",
            "--preview-seconds", "0.5",
        ],
        remappings=[
            (
                "/unity/assembly/start",
                "/mock_db_mvp/internal/assembly/start",
            ),
            (
                "/unity/assembly/feedback",
                "/mock_db_mvp/internal/assembly/feedback",
            ),
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument("endpoint_ip", default_value="0.0.0.0"),
        DeclareLaunchArgument("endpoint_port", default_value="10000"),
        DeclareLaunchArgument("start_delay", default_value="5"),
        DeclareLaunchArgument("inspection_fail_probability", default_value="0.2"),
        DeclareLaunchArgument("random_seed", default_value="-1"),
        DeclareLaunchArgument(
            "recipe",
            default_value=f"{package_share}/config/recipes/assembly-r1.yaml",
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                f"{existing_package}/launch/demo.launch.py"
            )
        ),
        Node(
            package="ros_tcp_endpoint",
            executable="default_server_endpoint",
            name="UnityEndpoint",
            output="screen",
            parameters=[
                {"ROS_IP": LaunchConfiguration("endpoint_ip")},
                {
                    "ROS_TCP_PORT": ParameterValue(
                        LaunchConfiguration("endpoint_port"), value_type=int
                    )
                },
            ],
        ),
        TimerAction(
            period=LaunchConfiguration("start_delay"), actions=[mock_node]
        ),
        Node(
            package="assembly_sequencer",
            executable="mock_node",
            name="assembly_sequencer_mock",
            output="screen",
            parameters=[{
                "recipe": LaunchConfiguration("recipe"),
                "inspection_fail_probability": ParameterValue(
                    LaunchConfiguration("inspection_fail_probability"),
                    value_type=float,
                ),
                "random_seed": ParameterValue(
                    LaunchConfiguration("random_seed"), value_type=int
                ),
            }],
        ),
    ])

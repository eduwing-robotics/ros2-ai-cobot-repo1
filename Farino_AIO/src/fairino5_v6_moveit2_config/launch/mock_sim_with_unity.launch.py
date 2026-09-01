from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def launch_mock(context):
    arguments = [
        "--velocity",
        LaunchConfiguration("velocity"),
        "--acceleration",
        LaunchConfiguration("acceleration"),
        "--preview-seconds",
        LaunchConfiguration("preview_seconds"),
        "--min-j3-deg",
        LaunchConfiguration("min_j3_deg"),
        "--max-step",
        LaunchConfiguration("max_step"),
        "--max-joint-step",
        LaunchConfiguration("max_joint_step"),
        "--recipe",
        LaunchConfiguration("recipe"),
    ]
    if LaunchConfiguration("listen_unity").perform(context).lower() in ("1", "true", "yes"):
        arguments.append("--listen-unity")
    else:
        arguments.extend([
            "--" + LaunchConfiguration("target_type").perform(context),
            *[LaunchConfiguration(f"target_{index}") for index in range(1, 7)],
        ])
    if LaunchConfiguration("plan_only").perform(context).lower() in ("1", "true", "yes"):
        arguments.append("--plan-only")

    return [
        Node(
            package="fairino5_v6_moveit2_config",
            executable="mock_sim.py",
            name="mock_movej",
            output="screen",
            arguments=arguments,
        )
    ]


def generate_launch_description():
    package_share = get_package_share_directory("fairino5_v6_moveit2_config")

    return LaunchDescription(
        [
            DeclareLaunchArgument("endpoint_ip", default_value="0.0.0.0"),
            DeclareLaunchArgument("endpoint_port", default_value="10000"),
            DeclareLaunchArgument("listen_unity", default_value="true"),
            DeclareLaunchArgument(
                "target_type", default_value="joints", choices=["joints", "pose"]
            ),
            DeclareLaunchArgument("target_1", default_value="90"),
            DeclareLaunchArgument("target_2", default_value="0"),
            DeclareLaunchArgument("target_3", default_value="0"),
            DeclareLaunchArgument("target_4", default_value="0"),
            DeclareLaunchArgument("target_5", default_value="0"),
            DeclareLaunchArgument("target_6", default_value="0"),
            DeclareLaunchArgument("velocity", default_value="10"),
            DeclareLaunchArgument("acceleration", default_value="10"),
            DeclareLaunchArgument("preview_seconds", default_value="2"),
            DeclareLaunchArgument("min_j3_deg", default_value="0"),
            DeclareLaunchArgument("max_step", default_value="0.005"),
            DeclareLaunchArgument("max_joint_step", default_value="0.35"),
            DeclareLaunchArgument(
                "recipe",
                description="AssemblySequencer-owned Recipe YAML path",
            ),
            DeclareLaunchArgument("plan_only", default_value="false"),
            DeclareLaunchArgument("start_delay", default_value="5"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    f"{package_share}/launch/demo.launch.py"
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
                period=LaunchConfiguration("start_delay"),
                actions=[OpaqueFunction(function=launch_mock)],
            ),
        ]
    )

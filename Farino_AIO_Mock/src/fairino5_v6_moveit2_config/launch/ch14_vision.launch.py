from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    start_robot_api = LaunchConfiguration("start_robot_api")

    return LaunchDescription(
        [
            DeclareLaunchArgument("start_robot_api", default_value="false"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution(
                        [FindPackageShare("realsense2_camera"), "launch", "rs_launch.py"]
                    )
                ),
                launch_arguments={
                    "rgb_camera.color_profile": "1920x1080x30",
                    "align_depth.enable": "true",
                }.items(),
            ),
            Node(
                package="fairino_hardware_v3_9_7",
                executable="ros2_cmd_server",
                output="screen",
                condition=IfCondition(start_robot_api),
            ),
        ]
    )

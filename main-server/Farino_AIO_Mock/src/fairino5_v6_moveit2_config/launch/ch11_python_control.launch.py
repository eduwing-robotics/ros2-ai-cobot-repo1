from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package="fairino_hardware_v3_9_7",
                executable="ros2_cmd_server",
                output="screen",
            )
        ]
    )

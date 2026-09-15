from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="vision_server",
            executable="orchestration_action_server",
            name="vision_orchestration_action_server",
            output="screen",
        ),
    ])

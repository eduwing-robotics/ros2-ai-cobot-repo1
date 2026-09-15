from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='vision_server',
            executable='conveyor_roi',
            name='conveyor_roi',
            output='screen',
        ),
    ])

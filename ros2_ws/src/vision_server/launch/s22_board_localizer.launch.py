from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='vision_server',
            executable='s22_board_localizer',
            name='s22_board_localizer',
            output='screen',
        ),
    ])

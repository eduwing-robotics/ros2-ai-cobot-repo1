from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='vision_server',
            executable='camera_manager',
            name='camera_manager',
            output='screen',
        ),
        Node(
            package='vision_server',
            executable='part_detector',
            name='part_detector',
            output='screen',
        ),
        Node(
            package='vision_server',
            executable='assembly_inspector',
            name='assembly_inspector',
            output='screen',
        ),
    ])
